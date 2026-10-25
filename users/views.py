from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated

from users.serializers import UserCreateSerializer, UserSerializer


@extend_schema(tags=["Users"], summary="Register a new user")
class CreateUserView(generics.CreateAPIView):
    serializer_class = UserCreateSerializer
    permission_classes = (AllowAny,)


@extend_schema(tags=["Users"])
@extend_schema_view(
    get=extend_schema(summary="Get the current user's profile"),
    put=extend_schema(summary="Update the current user's profile"),
    patch=extend_schema(summary="Partially update the current user's profile"),
)
class DetailUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user
