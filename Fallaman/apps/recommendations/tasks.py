from celery import shared_task

from apps.recommendations.services import expire_recommendations


@shared_task
def expire_recommendation_boosts():
    return expire_recommendations()
