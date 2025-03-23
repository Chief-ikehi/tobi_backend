from datetime import date

def has_active_membership(user):
    if not user.membership_tier or not user.membership_expires_at:
        return False
    return user.membership_expires_at >= date.today()
