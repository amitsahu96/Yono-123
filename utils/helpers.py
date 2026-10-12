import asyncio
import aiohttp
import time
import globals
from config import FOUR_SIM_API_KEY
from utils.google_sheet import get_ist_time
from spyeye import spyeye_client


async def log_game_metric(game_name, status="success"):
    async with globals.stats_lock:
        if game_name not in globals.live_stats["game_analytics"]:
            globals.live_stats["game_analytics"][game_name] = {
                "success": 0,
                "failed": 0,
                "already": 0,
            }
        if status == "success":
            globals.live_stats["game_analytics"][game_name]["success"] += 1
        elif status == "already":
            globals.live_stats["game_analytics"][game_name]["already"] += 1
        else:
            globals.live_stats["game_analytics"][game_name]["failed"] += 1


async def add_error_log(phone, game_name, error_reason):
    async with globals.stats_lock:
        globals.live_stats["error_logs"].insert(
            0,
            {
                "time": get_ist_time(),
                "phone": phone,
                "game": game_name,
                "reason": error_reason,
            },
        )
        if len(globals.live_stats["error_logs"]) > 50:
            globals.live_stats["error_logs"].pop()


async def add_timeline_event(phone, stage):
    async with globals.stats_lock:
        globals.live_stats["activity_timeline"].insert(
            0, {"time": get_ist_time(), "phone": phone, "stage": stage}
        )
        if len(globals.live_stats["activity_timeline"]) > 30:
            globals.live_stats["activity_timeline"].pop()


async def update_live_status(
    phone,
    status_text,
    balance_text=None,
    log_type="active",
    target_game=None,
    retry_idx=None,
    progress_val=None,
    otp_timeout_remaining=None,
    otp_timeout_total=None,
    queue_remaining=None,
):
    async with globals.stats_lock:
        for num_entry in globals.live_stats["recent_activity"]:
            if num_entry["phone"] == phone:
                num_entry["status"] = status_text
                num_entry["log_type"] = log_type
                if balance_text is not None:
                    num_entry["balance"] = balance_text
                if target_game is not None:
                    num_entry["current_game"] = target_game
                if retry_idx is not None:
                    num_entry["retry"] = retry_idx
                if progress_val is not None:
                    num_entry["progress"] = progress_val
                if otp_timeout_remaining is not None:
                    num_entry["otp_timeout_remaining"] = max(0, int(otp_timeout_remaining))
                elif status_text not in ("OTP Waiting", "Sending OTP..."):
                    num_entry["otp_timeout_remaining"] = None
                if otp_timeout_total is not None:
                    num_entry["otp_timeout_total"] = int(otp_timeout_total)
                if queue_remaining is not None:
                    num_entry["queue_remaining"] = max(0, int(queue_remaining))
                elif not status_text.startswith("Release Hold"):
                    num_entry["queue_remaining"] = None
                break


async def remove_recent_activity(phone):
    async with globals.stats_lock:
        globals.live_stats["recent_activity"] = [
            x for x in globals.live_stats["recent_activity"] if x["phone"] != phone
        ]


async def terminate_gateway_order_async(
    txn_id, otp_received, phone, force_cancel=False
):
    """Finish/cancel the provider order with strict 8-attempt cancellation.

    For 4SIM a cancel is considered successful only when the provider response
    explicitly says the number was cancelled (or was already cancelled).
    Transient/error/unknown responses are retried up to 8 total attempts.
    """
    async with globals.stats_lock:
        if txn_id in globals.logged_cancels:
            return "Already Handled"

    async with aiohttp.ClientSession() as session:
        if globals.global_provider == "otpdoctor":
            status_val = "8" if (force_cancel and not otp_received) else "6"
            url = f"https://otpdoctor.in/stubs/handler_api.php?action=setStatus&api_key={globals.global_otpdoctor_api_key}&id={txn_id}&status={status_val}"
            try:
                async with session.get(url, timeout=10) as response:
                    raw_text = (await response.text()).strip()
                    raw_lower = raw_text.lower()
                    async with globals.stats_lock:
                        globals.logged_cancels.add(txn_id)
                        is_cancel_success = status_val == "8" and any(
                            x in raw_lower for x in (
                                "access_cancel", "cancel successful", "already cancel", "already cancelled"
                            )
                        )
                        if is_cancel_success:
                            globals.live_stats["cancelled_orders"] += 1
                        globals.live_stats["cancel_logs"].insert(
                            0,
                            {
                                "phone": phone,
                                "txn_id": txn_id,
                                "status": "Released" if is_cancel_success else ("Finished Successfully" if status_val == "6" else "Failed"),
                                "response": raw_text or "No response",
                                "attempts": 1,
                                "time": get_ist_time(),
                                "provider": "OTPDoctor",
                            },
                        )
                        if len(globals.live_stats["cancel_logs"]) > 200:
                            globals.live_stats["cancel_logs"].pop()
                    return "Released" if status_val == "8" else "Finished Successfully"
            except Exception as exc:
                async with globals.stats_lock:
                    globals.live_stats["cancel_logs"].insert(
                        0,
                        {
                            "phone": phone,
                            "txn_id": txn_id,
                            "status": "Failed",
                            "response": str(exc) or "Request error",
                            "attempts": 1,
                            "time": get_ist_time(),
                            "provider": "OTPDoctor",
                        },
                    )
                    if len(globals.live_stats["cancel_logs"]) > 200:
                        globals.live_stats["cancel_logs"].pop()
                return "Failed"

        is_cancel = force_cancel and not otp_received
        if is_cancel:
            url = f"https://api.4sim.st/cancelNumber?apikey={FOUR_SIM_API_KEY}&id={txn_id}"
        else:
            url = f"https://api.4sim.st/finishOrder?apikey={FOUR_SIM_API_KEY}&id={txn_id}"

        max_attempts = 8 if is_cancel else 1
        final_status = "Failed Completely"
        last_response = ""

        for attempt in range(1, max_attempts + 1):
            try:
                async with session.get(url, timeout=10) as response:
                    raw_text = (await response.text()).strip()
                    raw_lower = raw_text.lower()
                    last_response = raw_text

                    # These are the only explicit 4SIM cancel-success signatures.
                    cancel_success = is_cancel and any(
                        x in raw_lower
                        for x in (
                            "cancel successful",
                            "number already cancel",
                            "number already cancelled",
                            "already cancel",
                            "already cancelled",
                        )
                    )
                    if cancel_success:
                        final_status = "Released"
                        break

                    if is_cancel and "cannot_cancel" in raw_lower:
                        final_status = "SMS_RECEIVED_CANNOT_CANCEL"
                    elif not is_cancel and any(
                        x in raw_lower
                        for x in ("finish successful", "finished successfully", "access_finish", "success")
                    ):
                        final_status = "Finished Successfully"
                        break
                    elif not is_cancel:
                        final_status = "Finished Successfully"
                        break

                    # Unknown/error response: retry cancellation.
                    final_status = "Failed Completely"
                    if attempt < max_attempts:
                        await update_live_status(
                            phone,
                            f"Cancel Retry {attempt + 1}/{max_attempts}",
                            log_type="cancel",
                        )
                        await asyncio.sleep(2)
            except Exception as exc:
                final_status = "Failed Completely"
                if attempt < max_attempts:
                    await update_live_status(
                        phone,
                        f"Cancel Retry {attempt + 1}/{max_attempts}",
                        log_type="cancel",
                    )
                    await asyncio.sleep(2)

        async with globals.stats_lock:
            if final_status in ("Released", "Finished Successfully"):
                globals.logged_cancels.add(txn_id)
                if is_cancel and final_status == "Released":
                    globals.live_stats["cancelled_orders"] += 1
                if is_cancel:
                    globals.live_stats["cancel_logs"].insert(
                        0,
                        {
                            "phone": phone,
                            "txn_id": txn_id,
                            "status": final_status,
                            "response": last_response or "Success",
                            "attempts": max_attempts if final_status == "Released" else 1,
                            "time": get_ist_time(),
                            "provider": "4SIM",
                        },
                    )
            elif final_status == "Failed Completely":
                globals.live_stats["cancel_failed_logs"] += 1
                failure_record = {
                    "phone": phone,
                    "txn_id": txn_id,
                    "attempts": max_attempts,
                    "response": last_response or "No response / request error",
                    "time": get_ist_time(),
                    "provider": "4SIM",
                }
                globals.live_stats["cancel_failed_numbers_list"].insert(0, failure_record)
                if is_cancel:
                    globals.live_stats["cancel_logs"].insert(
                        0,
                        {
                            **failure_record,
                            "status": "Failed Completely",
                        },
                    )

            if len(globals.live_stats["cancel_logs"]) > 200:
                del globals.live_stats["cancel_logs"][200:]

        return final_status


async def delayed_cancel_after_proxy_errors(phone, txn_id, delay_seconds=130):
    """Keep a 4SIM primary-game proxy-error number in a visible 130s queue."""
    queue_item = {
        "phone": phone,
        "txn_id": txn_id,
        "remaining": int(delay_seconds),
        "total": int(delay_seconds),
        "status": "Waiting for delayed cancel",
    }
    async with globals.stats_lock:
        globals.live_stats["delayed_cancel_queue"].append(queue_item)

    task = asyncio.current_task()
    globals.delayed_cancel_tasks.add(task)
    try:
        deadline = time.monotonic() + delay_seconds
        while queue_item["remaining"] > 0 and not globals.stop_event.is_set():
            async with globals.stats_lock:
                queue_item["remaining"] = max(0, int(deadline - time.monotonic() + 0.999))
            await asyncio.sleep(1)
        if globals.stop_event.is_set():
            queue_item["status"] = "Stop requested - cancelling"
        else:
            queue_item["remaining"] = 0
            queue_item["status"] = "Cancelling..."

        result = await terminate_gateway_order_async(
            txn_id, otp_received=False, phone=phone, force_cancel=True
        )
        queue_item["status"] = (
            "Cancel successful" if result == "Released"
            else "Cancel failed after 8 attempts" if result == "Failed Completely"
            else result
        )
        await add_timeline_event(phone, f"Delayed 4SIM Cancel -> {queue_item['status']}")
    finally:
        async with globals.stats_lock:
            globals.live_stats["delayed_cancel_queue"] = [
                item for item in globals.live_stats["delayed_cancel_queue"]
                if item.get("txn_id") != txn_id
            ]
        globals.delayed_cancel_tasks.discard(task)


async def complete_number_once(
    phone,
    txn_id,
    active_requests_tracker,
    poller_stop_event,
    number_state,
    reason,
):
    """Atomically complete one provider number and clean all pending work.

    The operation is idempotent: only the first caller performs provider/order
    cleanup. All pending SpyEye requests are cancelled and their waiting
    futures are released so foreground callers cannot continue processing OTPs.
    """
    lock = number_state["completion_lock"]
    async with lock:
        if number_state.get("number_completed"):
            return False

        number_state["number_completed"] = True
        number_state["completion_reason"] = reason
        poller_stop_event.set()

        otp_received = bool(number_state.get("otp_received_anywhere"))

        # Stop every pending game request for this number.
        async with aiohttp.ClientSession() as session:
            for game_key, track in list(active_requests_tracker.items()):
                if track.get("otp_received"):
                    otp_received = True

                # A request that already completed successfully/already/timeout
                # does not need another SpyEye cancel, but it still must be
                # removed from both trackers.
                if not track.get("completed"):
                    request_id = track.get("request_id")
                    api_name = track.get("api_name")
                    if request_id and api_name:
                        try:
                            await spyeye_client.cancel_request(
                                session, api_name, request_id
                            )
                        except Exception:
                            pass

                    if track.get("background_mode"):
                        async with globals.background_lock:
                            globals.background_active_tasks = max(
                                0, globals.background_active_tasks - 1
                            )

                    track["completed"] = True

                track["cleanup_done"] = True
                future = track.get("result_future")
                if future is not None and not future.done():
                    future.set_result(("number_complete", False, "0 INR"))

                async with globals.tracker_lock:
                    globals.global_active_requests_tracker.pop(
                        f"{phone}_{game_key}", None
                    )

            active_requests_tracker.clear()

        # One gateway order belongs to the number. Finish it when an OTP was
        # received; otherwise cancel/release it. This call is protected by the
        # number completion lock, so duplicate completion paths cannot repeat it.
        try:
            await terminate_gateway_order_async(
                txn_id,
                otp_received=otp_received,
                phone=phone,
                force_cancel=not otp_received,
            )
        except Exception:
            pass

        await update_live_status(
            phone,
            f"Number COMPLETE ({reason})",
            progress_val=100,
        )
        await add_timeline_event(phone, f"Number COMPLETE -> {reason}")
        return True


async def handle_already_number(phone, txn_id, otp_flag):
    current_task = asyncio.current_task()
    globals.active_already_tasks.add(current_task)

    async with globals.stats_lock:
        globals.live_stats["realtime_already_logs"] = len(
            globals.active_already_tasks
        )

    try:
        remaining_seconds = 136
        await update_live_status(
            phone,
            "Release Hold — 136s",
            log_type="already",
            queue_remaining=remaining_seconds,
        )
        await add_timeline_event(
            phone,
            "Moved to Delayed Queue (Already Reg - 2 Mins 16 Sec Hold)",
        )

        deadline = time.monotonic() + remaining_seconds
        while remaining_seconds > 0:
            remaining_seconds = max(0, int(deadline - time.monotonic() + 0.999))
            await update_live_status(
                phone,
                f"Release Hold — {remaining_seconds}s",
                log_type="already",
                queue_remaining=remaining_seconds,
            )
            await asyncio.sleep(1)

        await terminate_gateway_order_async(
            txn_id, otp_flag, phone, force_cancel=True
        )
        await update_live_status(phone, "Cool-off Completed", log_type="cancel")
    except Exception:
        pass
    finally:
        globals.active_already_tasks.discard(current_task)
        async with globals.stats_lock:
            globals.live_stats["realtime_already_logs"] = len(
                globals.active_already_tasks
            )
        await remove_recent_activity(phone)
