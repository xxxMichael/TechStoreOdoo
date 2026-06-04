# -*- coding: utf-8 -*-
"""
PRUEBAS UNITARIAS — Módulo ts.technician
=========================================
Cubre RF-07, RF-08, RF-09, RF-10
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestTechnician(TransactionCase):
    """Pruebas unitarias para el modelo ts.technician"""

    def setUp(self):
        super().setUp()
        self.technician = self.env['ts.technician'].create({
            'name': 'Ana García López',
            'employee_number': 'T-AGL-001',
            'specialty_hardware': True,
            'specialty_software': True,
            'email': 'ana.garcia@techstore.com',
        })
        self.client = self.env['res.partner'].create({'name': 'Empresa Demo'})
        self.service_type = self.env['ts.service.type'].create({'name': 'Reparación Test'})
        self.equipment = self.env['ts.equipment'].create({
            'name': 'Desktop Demo',
            'equipment_type': 'desktop',
            'brand': 'Dell',
            'model_name': 'OptiPlex 7090',
            'serial_number': 'SN-TECH-TEST-001',
            'client_id': self.client.id,
        })

    # ── CP-13: Registrar técnico con especialidades (RF-07) ───────────────
    def test_13_create_technician_with_specialties(self):
        """CP-13 | RF-07 | Técnico creado con especialidades hardware y software"""
        self.assertEqual(self.technician.name, 'Ana García López')
        self.assertTrue(self.technician.specialty_hardware)
        self.assertTrue(self.technician.specialty_software)
        self.assertFalse(self.technician.specialty_networks)
        self.assertEqual(self.technician.state, 'active')

    # ── CP-14: Número de empleado único (RF-07) ────────────────────────────
    def test_14_employee_number_unique_constraint(self):
        """CP-14 | RF-07 | Número de empleado duplicado → IntegrityError (sql constraint)"""
        from psycopg2 import IntegrityError
        with self.assertRaises(IntegrityError):
            self.env['ts.technician'].create({
                'name': 'Otro Técnico',
                'employee_number': 'T-AGL-001',  # duplicado
            })

    # ── CP-15: Métricas de carga de trabajo (RF-08, RF-09) ────────────────
    def test_15_workload_metrics(self):
        """CP-15 | RF-08/RF-09 | Métricas calculadas correctamente al asignar orden"""
        self.assertEqual(self.technician.active_order_count, 0)
        self.assertEqual(self.technician.completed_order_count, 0)

        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
            'technician_id': self.technician.id,
        })
        self.technician._compute_order_metrics()
        self.assertEqual(self.technician.active_order_count, 1, "Debe contar 1 orden activa")

    # ── CP-16: Cerrar orden actualiza métricas (RF-09) ────────────────────
    def test_16_closed_order_updates_completed_count(self):
        """CP-16 | RF-09 | Al cerrar orden, completed_order_count incrementa"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
            'technician_id': self.technician.id,
        })
        # Ciclo completo
        order.action_start_diagnosis()
        order.diagnosis = 'Batería agotada.'
        order.action_start_repair()
        order.resolution = 'Reemplazo de batería.'
        order.action_mark_ready()
        order.action_mark_delivered()
        order.action_close()

        self.technician._compute_order_metrics()
        self.assertEqual(self.technician.completed_order_count, 1)
        self.assertGreaterEqual(self.technician.avg_resolution_days, 0)

    # ── CP-17: Desactivar técnico sin órdenes activas (RF-10) ─────────────
    def test_17_deactivate_technician_no_active_orders(self):
        """CP-17 | RF-10 | Técnico sin órdenes activas puede desactivarse"""
        self.technician.action_deactivate()
        self.assertEqual(self.technician.state, 'inactive')
        self.assertEqual(self.technician.availability, 'busy')

    # ── CP-18: Desactivar técnico CON órdenes activas (RF-10) ─────────────
    def test_18_deactivate_technician_with_active_orders(self):
        """CP-18 | RF-10 | Técnico con órdenes activas NO puede desactivarse → UserError"""
        self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
            'technician_id': self.technician.id,
        })
        with self.assertRaises(UserError, msg="No debe poder desactivar técnico con órdenes activas"):
            self.technician.action_deactivate()

    # ── CP-19: Reactivar técnico (RF-10) ──────────────────────────────────
    def test_19_reactivate_technician(self):
        """CP-19 | RF-10 | Técnico inactivo puede reactivarse"""
        self.technician.state = 'inactive'
        self.technician.action_activate()
        self.assertEqual(self.technician.state, 'active')
        self.assertEqual(self.technician.availability, 'available')

    # ── CP-20: Tasa de reincidencia (RF-09) ───────────────────────────────
    def test_20_recurrence_rate_calculation(self):
        """CP-20 | RF-09 | Tasa de reincidencia = 0% cuando ninguna orden fue reabierta"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'No enciende',
            'physical_condition': 'Sin daños.',
            'technician_id': self.technician.id,
        })
        order.action_start_diagnosis()
        order.diagnosis = 'Falla en RAM.'
        order.action_start_repair()
        order.resolution = 'Reemplazo de RAM.'
        order.action_mark_ready()
        order.action_mark_delivered()
        order.action_close()

        self.technician._compute_order_metrics()
        self.assertEqual(self.technician.recurrence_rate, 0.0,
                         "Sin órdenes reabiertas, tasa de reincidencia debe ser 0%")
