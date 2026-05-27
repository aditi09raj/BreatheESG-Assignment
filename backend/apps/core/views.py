from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth.models import User
from .models import Tenant
from .serializers import TenantSerializer


class MeView(APIView):
    def get(self, request):
        user = request.user
        tenant = Tenant.objects.first()
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_staff': user.is_staff,
            'tenant': TenantSerializer(tenant).data if tenant else None,
        })
