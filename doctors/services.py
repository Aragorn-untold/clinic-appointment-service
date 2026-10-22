from datetime import date, time, datetime, timedelta


def generate_slots(
    workday: date, start_time: time, end_time: time, slot_length_minutes: int
) -> list[tuple[datetime, datetime]]:
    """Split a working period on a given day into consecutive slots.

    Slots are half-open intervals [start, end) that follow each other
    without gaps: the end of one slot is the start of the next. Generation
    starts at ``start_time``; a remainder shorter than ``slot_length_minutes``
    is dropped, so no slot ever ends after ``end_time``. For example,
    09:00-10:45 with 30-minute slots gives 09:00-09:30, 09:30-10:00 and
    10:00-10:30.

    The function does not touch the database and does not check for
    overlaps with existing slots; that is the caller's responsibility.

    Args:
        workday: Date of the slots.
        start_time: Start of the working period (local wall-clock time).
        end_time: End of the working period (local wall-clock time).
        slot_length_minutes: Length of one slot in minutes.

    Returns:
        A list of ``(start, end)`` tuples of naive datetimes. Attach the
        time zone (e.g. with ``django.utils.timezone.make_aware``) before
        saving them to the database. The list is empty if a single slot
        does not fit into the working period.

    Raises:
        ValueError: If ``start_time`` is not earlier than ``end_time``.
        ValueError: If ``slot_length_minutes`` is less than 1.
    """
    if start_time >= end_time:
        raise ValueError("start_time must be earlier than end_time")
    if slot_length_minutes < 1:
        raise ValueError(
            f"slot_length_minutes must be positive, got {slot_length_minutes}"
        )

    day_start = datetime.combine(workday, start_time)
    day_end = datetime.combine(workday, end_time)
    slot_length = timedelta(minutes=slot_length_minutes)
    slot_start = day_start

    result = []
    while slot_start + slot_length <= day_end:
        slot_end = slot_start + slot_length
        result.append((slot_start, slot_end))
        slot_start += slot_length

    return result
