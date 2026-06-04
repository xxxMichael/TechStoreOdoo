# -*- coding: utf-8 -*-
"""
PRUEBAS UNITARIAS — Módulo ts.maintenance.order
================================================
Cubre RF-01, RF-02, RF-03, RF-04, RF-05, RF-06
Metodología: Caja Negra — Partición de Equivalencias y Valores Límite
"""
import time
from datetime import date, timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from psycopg2 import IntegrityError


class TestMaintenanceOrderCreation(TransactionCase):
    """RF-01: Crear Orden de Mantenimiento"""

    def setUp(self):
        super().setUp()
        # Datos de prueba reutilizables
        self.client = self.env['res.partner'].create({
            'name': 'Cliente Test SA',
            'is_company': True,
        })
        self.service_type = self.env['ts.service.type'].create({
            'name': 'Diagnóstico Test',
        })
        self.technician = self.env['ts.technician'].create({
            'name': 'Técnico Test',
            'employee_number': 'T-TEST-001',
            'specialty_hardware': True,
        })
        self.equipment = self.env['ts.equipment'].create({
            'name': 'Laptop Test',
            'equipment_type': 'laptop',
            'brand': 'HP',
            'model_name': 'ProBook 450 G8',
            'serial_number': 'SN-UNIT-TEST-001',
            'client_id': self.client.id,
        })

    # ── CP-01: Crear orden con datos válidos ─────────────────────────────
    def test_01_create_order_valid_data(self):
        """CP-01 | RF-01 | Crear orden con todos los campos válidos → folio único"""
        start = time.time()
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'El equipo no enciende al presionar el botón de poder.',
            'physical_condition': 'Sin daños externos visibles, pantalla intacta.',
        })
        elapsed = time.time() - start

        self.assertNotEqual(order.folio, 'Nuevo', "El folio debe ser generado automáticamente")
        self.assertTrue(order.folio.startswith('TS-'), "El folio debe iniciar con 'TS-'")
        self.assertEqual(order.state, 'received', "Estado inicial debe ser 'received'")
        self.assertLess(elapsed, 2.0, f"Creación de orden tardó {elapsed:.3f}s (umbral: 2s)")

    # ── CP-02: Campos obligatorios ausentes ──────────────────────────────
    def test_02_create_order_missing_required_fields(self):
        """CP-02 | RF-01 | Intentar crear orden sin 'problem_description' → IntegrityError"""
        with self.assertRaises(IntegrityError):
            self.env['ts.maintenance.order'].create({
                'client_id': self.client.id,
                'equipment_id': self.equipment.id,
                'service_type_id': self.service_type.id,
                # problem_description AUSENTE — campo required
                'physical_condition': 'Sin daños.',
            })

    # ── CP-03: Folio único — no se repite ────────────────────────────────
    def test_03_folio_is_unique_per_order(self):
        """CP-03 | RF-01 | Dos órdenes creadas tienen folios distintos"""
        base = {
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'Problema A',
            'physical_condition': 'Sin daños.',
        }
        order1 = self.env['ts.maintenance.order'].create(dict(base))
        order2 = self.env['ts.maintenance.order'].create(dict(base, problem_description='Problema B'))
        self.assertNotEqual(order1.folio, order2.folio, "Los folios deben ser únicos")

    # ── CP-04: Fecha de recepción futura rechazada ────────────────────────
    def test_04_future_reception_date_rejected(self):
        """CP-04 | RF-01 | Fecha futura en recepción → ValidationError"""
        with self.assertRaises(ValidationError):
            self.env['ts.maintenance.order'].create({
                'client_id': self.client.id,
                'equipment_id': self.equipment.id,
                'service_type_id': self.service_type.id,
                'problem_description': 'Pantalla rota',
                'physical_condition': 'Pantalla dañada.',
                'reception_date': date.today() + timedelta(days=5),
            })

    # ── CP-05: Asignar técnico (RF-02) ────────────────────────────────────
    def test_05_assign_technician(self):
        """CP-05 | RF-02 | Asignar técnico activo a orden existente"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
        })
        order.technician_id = self.technician.id
        self.assertEqual(order.technician_id.id, self.technician.id)
        # Verificar que se generó un log de auditoría al crear
        self.assertTrue(order.audit_log_ids, "Debe existir al menos un registro en el log de auditoría")

    # ── CP-06: Avanzar estado sin técnico → UserError (RF-03) ─────────────
    def test_06_advance_state_without_technician(self):
        """CP-06 | RF-03 | Intentar diagnóstico sin técnico asignado → UserError"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
        })
        with self.assertRaises(UserError, msg="Debe lanzar UserError si no hay técnico asignado"):
            order.action_start_diagnosis()

    # ── CP-07: Ciclo de vida completo (RF-03) ─────────────────────────────
    def test_07_full_lifecycle(self):
        """CP-07 | RF-03 | Recorrer todos los estados del ciclo de vida"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'Pantalla rota',
            'physical_condition': 'Pantalla dañada.',
            'technician_id': self.technician.id,
        })
        self.assertEqual(order.state, 'received')

        order.action_start_diagnosis()
        self.assertEqual(order.state, 'diagnosis')

        order.diagnosis = 'Pantalla LCD dañada por impacto.'
        order.action_start_repair()
        self.assertEqual(order.state, 'repair')

        order.resolution = 'Se reemplazó la pantalla LCD por pantalla nueva original.'
        order.action_mark_ready()
        self.assertEqual(order.state, 'ready')

        order.action_mark_delivered()
        self.assertEqual(order.state, 'delivered')
        self.assertIsNotNone(order.delivery_date, "Debe registrar la fecha de entrega")

        order.action_close()
        self.assertEqual(order.state, 'closed')
        self.assertIsNotNone(order.close_date, "Debe registrar la fecha de cierre")

    # ── CP-08: Orden cerrada no editable (RF-06) ──────────────────────────
    def test_08_closed_order_not_editable(self):
        """CP-08 | RF-06 | Intentar cambiar estado de orden cerrada → UserError"""
        order = self._create_closed_order()
        with self.assertRaises(UserError, msg="Orden cerrada no debe poder modificarse"):
            order.action_start_diagnosis()

    # ── CP-09: Prioridad crítica visible (RF-04) ──────────────────────────
    def test_09_critical_priority_flag(self):
        """CP-09 | RF-04 | Prioridad crítica activa el campo priority_kanban"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'Sistema caído producción',
            'physical_condition': 'Sin daños físicos.',
            'priority': '3',
        })
        self.assertTrue(order.priority_kanban, "Prioridad Crítica debe activar priority_kanban=True")

    # ── CP-10: Diagnóstico requerido antes de reparación (RF-05) ──────────
    def test_10_diagnosis_required_before_repair(self):
        """CP-10 | RF-05 | Avanzar a reparación sin diagnóstico → UserError"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
            'technician_id': self.technician.id,
        })
        order.action_start_diagnosis()
        # Sin escribir order.diagnosis, intentar avanzar
        with self.assertRaises(UserError, msg="Debe requerir diagnóstico antes de reparación"):
            order.action_start_repair()

    # ── CP-11: Resolución requerida antes de "listo" (RF-05) ──────────────
    def test_11_resolution_required_before_ready(self):
        """CP-11 | RF-05 | Marcar listo sin resolución → UserError"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
            'technician_id': self.technician.id,
        })
        order.action_start_diagnosis()
        order.diagnosis = 'Falla en fuente de poder.'
        order.action_start_repair()
        # Sin escribir order.resolution
        with self.assertRaises(UserError, msg="Debe requerir resolución antes de marcar listo"):
            order.action_mark_ready()

    # ── CP-12: days_open se calcula correctamente ─────────────────────────
    def test_12_days_open_calculation(self):
        """CP-12 | RF-01 | Campo days_open calculado desde fecha de recepción"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
            'reception_date': date.today() - timedelta(days=5),
        })
        self.assertEqual(order.days_open, 5, "days_open debe ser 5 para una orden recibida hace 5 días")

    # ── Helper privado ─────────────────────────────────────────────────────
    def _create_closed_order(self):
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
            'technician_id': self.technician.id,
        })
        order.action_start_diagnosis()
        order.diagnosis = 'Falla en placa.'
        order.action_start_repair()
        order.resolution = 'Reemplazo de placa madre.'
        order.action_mark_ready()
        order.action_mark_delivered()
        order.action_close()
        return order
