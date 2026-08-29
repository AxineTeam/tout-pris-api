from allauth.headless.adapter import DefaultHeadlessAdapter


class HeadlessAdapter(DefaultHeadlessAdapter):
    def serialize_user(self, user):
        return {**super().serialize_user(user), "language": user.language}
