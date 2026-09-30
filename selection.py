"""Task selection is independent of priority ordering and server progress."""
from constants import PriorityMode


def campaign_selected(settings, campaign):
    if campaign.id in getattr(settings, 'cancelled_campaigns', set()):
        return False
    if campaign.game.name in settings.exclude:
        return False
    return (settings.priority_mode is not PriorityMode.PRIORITY_ONLY
            or campaign.game.name in settings.priority
            or campaign.id in getattr(settings, 'selected_campaigns', set()))
