# -*- coding: utf-8 -*-
"""
PRUEBAS UNITARIAS — Módulos ts.equipment y ts.audit.log
=========================================================
Cubre RF-11, RF-12, RF-13, RF-15
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError, AccessError


class TestEquipment(TransactionCase):
    """Pruebas unitarias para el modelo ts.equipment"""

    def setUp(self):
        super().setUp()
        self.client = self.env['res.partner'].create({'name': 'Cliente Equipo Test'})
        self.client2 = self.env['res.partner'].create({'name': 'Segundo Cliente'})

    # ── CP-21: Registrar equipo con campos completos (RF-11) ──────────────
    def test_21_create_equipment_valid(self):
        """CP-21 | RF-11 | Registrar equipo con todos los campos obligatorios"""
        equipment = self.env['ts.equipment'].create({
            'name': 'Laptop Gerencia',
            'equipment_type': 'laptop',
            'brand': 'Lenovo',
            'model_name': 'ThinkPad X1 Carbon',
            'serial_number': 'SN-EQ-VALID-001',
            'client_id': self.client.id,
        })
        self.assertEqual(equipment.current_state, 'operational')
        self.assertTrue(equipment.active)
        self.assertEqual(equipment.order_count, 0)

    # ── CP-22: Número de serie duplicado rechazado (RF-11) ────────────────
    def test_22_serial_number_duplicate_rejected(self):
        """
        CP-22 | RF-11 | Serial duplicado lanza excepción.
        Nota técnica: los _sql_constraints de Odoo generan psycopg2.errors.UniqueViolation
        a nivel de BD (antes de que @api.constrains pueda convertirlo a ValidationError),
        por eso se captura con Exception en lugar de ValidationError.
        """
        self.env['ts.equipment'].create({
            'name': 'Laptop 1',
            'equipment_type': 'laptop',
            'brand': 'HP',
            'model_name': 'EliteBook 840',
            'serial_number': 'SN-DUPLICADO-001',
            'client_id': self.client.id,
        })
        with self.assertRaises(Exception):  # psycopg2.UniqueViolation o ValidationError
            self.env['ts.equipment'].create({
                'name': 'Laptop 2',
                'equipment_type': 'laptop',
                'brand': 'Dell',
                'model_name': 'Latitude 5520',
                'serial_number': 'SN-DUPLICADO-001',  # duplicado
                'client_id': self.client2.id,
            })

    # ── CP-23: name_get formatea correctamente (RF-11) ────────────────────
    def test_23_name_get_format(self):
        """CP-23 | RF-11 | name_get debe incluir serial, marca, modelo y cliente"""
        equipment = self.env['ts.equipment'].create({
            'name': 'Equipo Prueba',
            'equipment_type': 'desktop',
            'brand': 'Dell',
            'model_name': 'OptiPlex 3080',
            'serial_number': 'SN-FORMAT-001',
            'client_id': self.client.id,
        })
        display = equipment.name_get()[0][1]
        self.assertIn('SN-FORMAT-001', display)
        self.assertIn('Dell', display)
        self.assertIn('Cliente Equipo Test', display)

    # ── CP-24: Historial de mantenimientos por equipo (RF-12) ─────────────
    def test_24_maintenance_history_count(self):
        """CP-24 | RF-12 | order_count refleja el número de mantenimientos del equipo"""
        equipment = self.env['ts.equipment'].create({
            'name': 'Servidor Test',
            'equipment_type': 'server',
            'brand': 'HP',
            'model_name': 'ProLiant DL380',
            'serial_number': 'SN-HIST-001',
            'client_id': self.client.id,
        })
        service_type = self.env['ts.service.type'].create({'name': 'Mantenimiento Preventivo'})
        self.assertEqual(equipment.order_count, 0)

        self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': equipment.id,
            'service_type_id': service_type.id,
            'problem_description': 'Mantenimiento rutinario',
            'physical_condition': 'Sin daños.',
        })
        equipment._compute_order_count()
        self.assertEqual(equipment.order_count, 1)

    # ── CP-25: Estado físico al ingreso requerido (RF-13) ─────────────────
    def test_25_physical_condition_required_in_order(self):
        """CP-25 | RF-13 | Crear orden sin estado físico → error de campo requerido"""
        equipment = self.env['ts.equipment'].create({
            'name': 'PC Prueba',
            'equipment_type': 'desktop',
            'brand': 'Acer',
            'model_name': 'Aspire TC',
            'serial_number': 'SN-PHYS-001',
            'client_id': self.client.id,
        })
        service_type = self.env['ts.service.type'].create({'name': 'Diagnóstico'})
        with self.assertRaises(Exception):
            self.env['ts.maintenance.order'].create({
                'client_id': self.client.id,
                'equipment_id': equipment.id,
                'service_type_id': service_type.id,
                'problem_description': 'No enciende',
                # physical_condition AUSENTE — campo required
            })


class TestAuditLog(TransactionCase):
    """Pruebas unitarias para el modelo ts.audit.log (RF-15)"""

    def setUp(self):
        super().setUp()
        self.client = self.env['res.partner'].create({'name': 'Cliente Audit Test'})
        self.service_type = self.env['ts.service.type'].create({'name': 'Servicio Audit'})
        self.technician = self.env['ts.technician'].create({
            'name': 'Técnico Audit',
            'employee_number': 'T-AUDIT-001',
        })
        self.equipment = self.env['ts.equipment'].create({
            'name': 'Equipo Audit',
            'equipment_type': 'laptop',
            'brand': 'HP',
            'model_name': 'Pavilion',
            'serial_number': 'SN-AUDIT-001',
            'client_id': self.client.id,
        })

    # ── CP-26: Log generado automáticamente al crear orden (RF-15) ────────
    def test_26_audit_log_created_on_order_creation(self):
        """CP-26 | RF-15 | Crear orden genera automáticamente entrada en audit_log"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'Falla de sistema',
            'physical_condition': 'Sin daños externos.',
        })
        self.assertTrue(order.audit_log_ids, "Debe existir al menos un log al crear la orden")
        log = order.audit_log_ids[0]
        self.assertEqual(log.order_id.id, order.id)
        self.assertIsNotNone(log.event_date)
        self.assertIsNotNone(log.user_id)

    # ── CP-27: Log generado al cambiar estado (RF-15) ─────────────────────
    def test_27_audit_log_on_state_change(self):
        """CP-27 | RF-15 | Cada transición de estado genera entrada en log"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
            'technician_id': self.technician.id,
        })
        logs_before = len(order.audit_log_ids)
        order.action_start_diagnosis()
        logs_after = len(order.audit_log_ids)
        self.assertGreater(logs_after, logs_before, "Cambio de estado debe generar nuevo log")

    # ── CP-28: Log inmutable — write bloqueado (RF-15) ────────────────────
    def test_28_audit_log_write_blocked(self):
        """CP-28 | RF-15 | Intentar editar registro de audit_log → AccessError"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
        })
        log = order.audit_log_ids[0]
        with self.assertRaises(AccessError, msg="El log de auditoría debe ser inmutable"):
            log.write({'description': 'Intentando modificar el log'})

    # ── CP-29: Log inmutable — unlink bloqueado (RF-15) ───────────────────
    def test_29_audit_log_unlink_blocked(self):
        """CP-29 | RF-15 | Intentar eliminar registro de audit_log → AccessError"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
        })
        log = order.audit_log_ids[0]
        with self.assertRaises(AccessError, msg="El log de auditoría no debe poder eliminarse"):
            log.unlink()
