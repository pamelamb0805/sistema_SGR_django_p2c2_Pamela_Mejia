
from django.test import TestCase
from django.db.models.deletion import ProtectedError

from .models import Catalog, Product


class CatalogModelTests(TestCase):

    def crear_catalogo(self, codigo="CAT-001", nombre="Catálogo de prueba"):
        return Catalog.objects.create(
            catalog_id=codigo,
            name=nombre,
            description="Descripción de prueba",
            status="Activo",
        )

    def test_crear_catalogo(self):
        catalogo = self.crear_catalogo()

        self.assertIsNotNone(catalogo.pk)
        self.assertEqual(catalogo.catalog_id, "CAT-001")
        self.assertEqual(catalogo.name, "Catálogo de prueba")

    def test_representacion_catalogo(self):
        catalogo = self.crear_catalogo()

        self.assertEqual(
            str(catalogo),
            "CAT-001 - Catálogo de prueba",
        )

    def test_codigo_catalogo_unico(self):
        self.crear_catalogo()

        with self.assertRaises(Exception):
            self.crear_catalogo(
                codigo="CAT-001",
                nombre="Otro catálogo",
            )

    def test_ordenamiento_por_nombre(self):
        self.crear_catalogo("CAT-002", "Zeta")
        self.crear_catalogo("CAT-003", "Alfa")

        nombres = list(
            Catalog.objects.values_list("name", flat=True)
        )

        self.assertEqual(nombres, sorted(nombres))


class ProductModelTests(TestCase):

    def setUp(self):
        self.catalogo = Catalog.objects.create(
            catalog_id="CAT-PROD",
            name="Catálogo de productos",
            description="Productos de prueba",
            status="Activo",
        )

    def crear_producto(
        self,
        codigo="PROD-001",
        sku="SKU-001",
        nombre="Producto de prueba",
    ):
        return Product.objects.create(
            product_id=codigo,
            name=nombre,
            description="Descripción del producto",
            kwh="12.50",
            manufacturer="Fabricante de prueba",
            model="Modelo de prueba",
            sku=sku,
            catalog=self.catalogo,
        )

    def test_crear_producto(self):
        producto = self.crear_producto()

        self.assertIsNotNone(producto.pk)
        self.assertEqual(producto.product_id, "PROD-001")
        self.assertEqual(producto.name, "Producto de prueba")
        self.assertEqual(producto.catalog, self.catalogo)

    def test_representacion_producto(self):
        producto = self.crear_producto()

        self.assertEqual(
            str(producto),
            "SKU-001 - Producto de prueba",
        )

    def test_producto_pertenece_a_catalogo(self):
        producto = self.crear_producto()

        self.assertEqual(
            self.catalogo.products.count(),
            1,
        )

        self.assertEqual(
            self.catalogo.products.first(),
            producto,
        )

    def test_codigo_producto_unico(self):
        self.crear_producto()

        with self.assertRaises(Exception):
            self.crear_producto(
                codigo="PROD-001",
                sku="SKU-002",
                nombre="Producto duplicado",
            )

    def test_sku_producto_unico(self):
        self.crear_producto()

        with self.assertRaises(Exception):
            self.crear_producto(
                codigo="PROD-002",
                sku="SKU-001",
                nombre="Producto duplicado",
            )

    def test_no_se_elimina_catalogo_con_productos_asociados(self):
        self.crear_producto()

        with self.assertRaises(ProtectedError):
            self.catalogo.delete()

        self.assertTrue(
            Catalog.objects.filter(pk=self.catalogo.pk).exists()
        )
