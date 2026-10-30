from django import template

from cod_location.models import PickupSchedule

register = template.Library()


@register.inclusion_tag("cod_location/partials/schedule_summary.html")
def cod_schedule_summary(loan):
    schedules = PickupSchedule.objects.filter(
        loan_request=loan
    ).select_related("cod_location")

    pickup = None
    return_schedule = None

    for schedule in schedules:
        if schedule.schedule_type == PickupSchedule.ScheduleType.PICKUP:
            pickup = schedule
        elif schedule.schedule_type == PickupSchedule.ScheduleType.RETURN:
            return_schedule = schedule

    return {
        "pickup": pickup,
        "return_schedule": return_schedule,
    }