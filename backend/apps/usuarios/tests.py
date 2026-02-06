from django.test import TestCase

from apps.usuarios.serializers import UsuarioSerializer


class UsuarioSerializerTests(TestCase):
    def test_create_asigna_modulos_vacio_cuando_no_se_envia(self):
        serializer = UsuarioSerializer(
            data={
                'username': 'sin_modulos',
                'password': 'pass1234',
                'tipo_usuario': 'ADMIN',
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        usuario = serializer.save()

        self.assertEqual(usuario.modulos_permitidos, {})

    def test_create_asigna_modulos_vacio_cuando_llega_null(self):
        serializer = UsuarioSerializer(
            data={
                'username': 'modulos_null',
                'password': 'pass1234',
                'tipo_usuario': 'VENDEDOR',
                'modulos_permitidos': None,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        usuario = serializer.save()

        self.assertEqual(usuario.modulos_permitidos, {})
