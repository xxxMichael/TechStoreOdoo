# -*- coding: utf-8 -*-
"""
PRUEBAS DE INTEGRACIÓN — TechStore Maintenance
===============================================
Verifica flujos completos multi-modelo, rendimiento y restricciones de seguridad.
Cubre RF-01..RF-20 en escenarios end-to-end.
"""
import time
from datetime import date, timedelta
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, AccessError, ValidationError


class TestIntegrationFullWorkflow(TransactionCase):
    """
    Pruebas de integración que simulan el flujo completo del taller:
    Recepción → Diagnóstico → Reparación → Entrega → Cierre
    con auditoría, métricas y múltiples actores involucrados.
    """

    def setUp(self):
        super().setUp()
        # ── Datos maestros ──
        self.client_a = self.env['res.partner'].create({'name': 'Corporativo Alpha SA'})
        self.client_b = self.env['res.partner'].create({'name': 'PyME Beta SRL'})

        self.svc_hardware = self.env['ts.service.type'].create({'name': 'Reparación Hardware'})
        self.svc_software = self.env['ts.service.type'].create({'name': 'Reinstalación Software'})

        self.tech1 = self.env['ts.technician'].create({
            'name': 'Carlos Ramírez',
            'employee_number': 'T-INT-001',
            'specialty_hardware': True,
        })
        self.tech2 = self.env['ts.technician'].create({
            'name': 'Laura Mendez',
            'employee_number': 'T-INT-002',
            'specialty_software': True,
        })
        self.laptop_a = self.env['ts.equipment'].create({
            'name': 'Laptop Gerente Alpha',
            'equipment_type': 'laptop',
            'brand': 'Dell',
            'model_name': 'XPS 15',
            'serial_number': 'SN-INT-ALPHA-001',
            'client_id': self.client_a.id,
        })
        self.desktop_b = self.env['ts.equipment'].create({
            'name': 'Desktop Recepción Beta',
            'equipment_type': 'desktop',
            'brand': 'Lenovo',
            'model_name': 'ThinkCentre M90',
            'serial_number': 'SN-INT-BETA-001',
            'client_id': self.client_b.id,
        })

    # ── CI-01: Flujo completo hardware (RF-01..06 + RF-15) ────────────────
    def test_ci_01_full_hardware_repair_workflow(self):
        """
        CI-01 | Integración | Flujo completo: Recepción → Cierre con auditoría
        Valida la correcta interacción entre ts.maintenance.order y ts.audit.log
        """
        # 1. Recepción
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client_a.id,
            'equipment_id': self.laptop_a.id,
            'service_type_id': self.svc_hardware.id,
            'problem_description': 'La laptop no reconoce el disco duro al arrancar.',
            'physical_condition': 'Carcasa con raspón leve en esquina inferior derecha.',
            'priority': '2',
            'technician_id': self.tech1.id,
        })
        self.assertEqual(order.state, 'received')
        logs_count = len(order.audit_log_ids)
        self.assertGreater(logs_count, 0)

        # 2. Diagnóstico
        order.action_start_diagnosis()
        self.assertEqual(order.state, 'diagnosis')
        order.diagnosis = 'Disco SSD dañado por sectores defectuosos. Datos parcialmente recuperables.'
        logs_count_2 = len(order.audit_log_ids)
        self.assertGreater(logs_count_2, logs_count)

        # 3. Reparación
        order.action_start_repair()
        self.assertEqual(order.state, 'repair')
        order.work_done = 'Sustitución de SSD por unidad nueva de 512GB.'
        order.parts_used = '1x SSD Samsung 970 EVO Plus 512GB'
        order.resolution = 'Instalación de SSD nuevo, restauración de respaldo de datos.'

        # 4. Listo para entrega
        order.action_mark_ready()
        self.assertEqual(order.state, 'ready')

        # 5. Entregado
        order.action_mark_delivered()
        self.assertEqual(order.state, 'delivered')
        self.assertEqual(order.delivery_date, date.today())

        # 6. Cierre
        order.action_close()
        self.assertEqual(order.state, 'closed')
        self.assertEqual(order.close_date, date.today())

        # Verificar log completo: debe tener entrada por cada transición
        self.assertGreaterEqual(len(order.audit_log_ids), 5)
        event_types = [log.event_type for log in order.audit_log_ids]
        self.assertIn('Orden creada', event_types)
        self.assertIn('Cambio de estado', event_types)
        self.assertIn('Orden cerrada', event_types)

        # Verificar métricas del técnico
        self.tech1._compute_order_metrics()
        self.assertEqual(self.tech1.completed_order_count, 1)
        self.assertEqual(self.tech1.active_order_count, 0)

    # ── CI-02: Múltiples órdenes — carga de trabajo (RF-08) ──────────────
    def test_ci_02_multiple_orders_workload(self):
        """
        CI-02 | Integración | Múltiples órdenes asignadas actualiza carga correctamente
        """
        orders = []
        for i in range(3):
            eq = self.env['ts.equipment'].create({
                'name': f'Equipo {i+1}',
                'equipment_type': 'laptop',
                'brand': 'HP',
                'model_name': f'Model {i+1}',
                'serial_number': f'SN-WKLD-00{i+1}',
                'client_id': self.client_b.id,
            })
            order = self.env['ts.maintenance.order'].create({
                'client_id': self.client_b.id,
                'equipment_id': eq.id,
                'service_type_id': self.svc_software.id,
                'problem_description': f'Problema {i+1}',
                'physical_condition': 'Sin daños.',
                'technician_id': self.tech2.id,
            })
            orders.append(order)

        self.tech2._compute_order_metrics()
        self.assertEqual(self.tech2.active_order_count, 3)

        # Cerrar una
        orders[0].action_start_diagnosis()
        orders[0].diagnosis = 'Malware detectado.'
        orders[0].action_start_repair()
        orders[0].resolution = 'Limpieza completa y reinstalación de SO.'
        orders[0].action_mark_ready()
        orders[0].action_mark_delivered()
        orders[0].action_close()

        self.tech2._compute_order_metrics()
        self.assertEqual(self.tech2.active_order_count, 2)
        self.assertEqual(self.tech2.completed_order_count, 1)

    # ── CI-03: Integridad referencial equipo-cliente (RF-11) ──────────────
    def test_ci_03_equipment_client_referential_integrity(self):
        """
        CI-03 | Integración | No se puede asignar equipo de un cliente a orden de otro
        (validado por domain en la vista, aquí validamos que el equipo registra el historial)
        """
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client_a.id,
            'equipment_id': self.laptop_a.id,
            'service_type_id': self.svc_hardware.id,
            'problem_description': 'Teclado dañado',
            'physical_condition': 'Teclas rotas.',
        })
        self.laptop_a._compute_order_count()
        self.assertEqual(self.laptop_a.order_count, 1,
                         "El historial del equipo debe reflejar la orden creada")

    # ── CI-04: Reasignación de técnico registrada en auditoría (RF-02, RF-15)
    def test_ci_04_technician_reassignment_logged(self):
        """
        CI-04 | Integración | Reasignación de técnico genera entrada en audit_log
        """
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client_b.id,
            'equipment_id': self.desktop_b.id,
            'service_type_id': self.svc_software.id,
            'problem_description': 'No inicia Windows',
            'physical_condition': 'Sin daños.',
            'technician_id': self.tech1.id,
        })
        logs_before = len(order.audit_log_ids)
        order.action_assign_technician(self.tech2.id)
        logs_after = len(order.audit_log_ids)
        self.assertGreater(logs_after, logs_before,
                           "Reasignación de técnico debe registrarse en audit_log")
        self.assertEqual(order.technician_id.id, self.tech2.id)

    # ── CI-05: Dashboard métricas ISO 25010 (RF-18, RF-20) ────────────────
    def test_ci_05_dashboard_iso_metrics(self):
        """
        CI-05 | Integración | Dashboard calcula métricas ISO en base a datos reales
        """
        # Crear y cerrar 2 órdenes (sin reincidencia)
        for i in range(2):
            eq = self.env['ts.equipment'].create({
                'name': f'Equipo Dashboard {i}',
                'equipment_type': 'desktop',
                'brand': 'HP',
                'model_name': f'Z{i}',
                'serial_number': f'SN-DASH-00{i}',
                'client_id': self.client_a.id,
            })
            order = self.env['ts.maintenance.order'].create({
                'client_id': self.client_a.id,
                'equipment_id': eq.id,
                'service_type_id': self.svc_hardware.id,
                'problem_description': f'Falla {i}',
                'physical_condition': 'Sin daños.',
                'technician_id': self.tech1.id,
            })
            order.action_start_diagnosis()
            order.diagnosis = 'Diagnóstico completado.'
            order.action_start_repair()
            order.resolution = 'Reparación exitosa.'
            order.action_mark_ready()
            order.action_mark_delivered()
            order.action_close()

        # Abrir dashboard
        dashboard = self.env['ts.dashboard'].create({})
        data = self.env['ts.dashboard'].default_get(list(self.env['ts.dashboard']._fields.keys()))

        self.assertGreaterEqual(data.get('count_closed', 0), 2)
        self.assertEqual(data.get('recurrence_rate', -1), 0.0,
                         "Sin reincidencias, tasa debe ser 0%")
        self.assertEqual(data.get('iso_correctness', 0), 100.0,
                         "Con 0% reincidencia, Correctness debe ser 100%")
        self.assertEqual(data.get('iso_correctness_semaphore'), 'green')


class TestPerformance(TransactionCase):
    """
    Pruebas de rendimiento — Tiempos de respuesta bajo carga.
    Mide operaciones críticas contra umbrales SLA definidos en RNF-01 y RNF-02.
    """

    def setUp(self):
        super().setUp()
        self.client = self.env['res.partner'].create({'name': 'Cliente Perf Test'})
        self.service_type = self.env['ts.service.type'].create({'name': 'Servicio Perf'})
        self.technician = self.env['ts.technician'].create({
            'name': 'Técnico Perf',
            'employee_number': 'T-PERF-001',
        })

    def _create_equipment(self, suffix):
        return self.env['ts.equipment'].create({
            'name': f'Equipo Perf {suffix}',
            'equipment_type': 'laptop',
            'brand': 'HP',
            'model_name': 'Test Model',
            'serial_number': f'SN-PERF-{suffix}',
            'client_id': self.client.id,
        })

    # ── PERF-01: Creación de orden ≤ 2s ───────────────────────────────────
    def test_perf_01_order_creation_time(self):
        """PERF-01 | Rendimiento | Crear orden debe completarse en < 2 segundos"""
        eq = self._create_equipment('P01')
        start = time.perf_counter()
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': eq.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'Test de rendimiento',
            'physical_condition': 'Sin daños.',
        })
        elapsed = time.perf_counter() - start
        self.assertIsNotNone(order.id)
        self.assertLess(elapsed, 2.0,
                        f"Creación de orden tardó {elapsed:.3f}s — Umbral SLA: 2s")

    # ── PERF-02: Búsqueda en lista de 50 órdenes ≤ 3s ────────────────────
    def test_perf_02_search_50_orders(self):
        """PERF-02 | Rendimiento | Búsqueda en 50 órdenes debe completarse en < 3 segundos"""
        # Crear 50 órdenes
        for i in range(50):
            eq = self._create_equipment(f'P02-{i:02d}')
            self.env['ts.maintenance.order'].create({
                'client_id': self.client.id,
                'equipment_id': eq.id,
                'service_type_id': self.service_type.id,
                'problem_description': f'Problema {i}',
                'physical_condition': 'Sin daños.',
            })

        start = time.perf_counter()
        orders = self.env['ts.maintenance.order'].search(
            [('client_id', '=', self.client.id)],
            order='reception_date desc'
        )
        elapsed = time.perf_counter() - start

        self.assertEqual(len(orders), 50)
        self.assertLess(elapsed, 3.0,
                        f"Búsqueda de 50 órdenes tardó {elapsed:.3f}s — Umbral SLA: 3s")

    # ── PERF-03: Ciclo de vida completo ≤ 5s ─────────────────────────────
    def test_perf_03_full_lifecycle_time(self):
        """PERF-03 | Rendimiento | Ciclo de vida completo (6 estados) en < 5 segundos"""
        eq = self._create_equipment('P03')
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': eq.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'Test lifecycle',
            'physical_condition': 'Sin daños.',
            'technician_id': self.technician.id,
        })

        start = time.perf_counter()
        order.action_start_diagnosis()
        order.diagnosis = 'Diagnóstico perf test.'
        order.action_start_repair()
        order.resolution = 'Resolución perf test.'
        order.action_mark_ready()
        order.action_mark_delivered()
        order.action_close()
        elapsed = time.perf_counter() - start

        self.assertEqual(order.state, 'closed')
        self.assertLess(elapsed, 5.0,
                        f"Ciclo completo tardó {elapsed:.3f}s — Umbral SLA: 5s")

    # ── PERF-04: Dashboard con 20 órdenes ≤ 3s ───────────────────────────
    def test_perf_04_dashboard_load_time(self):
        """PERF-04 | Rendimiento | Cargar dashboard con 20 órdenes en < 3 segundos"""
        for i in range(20):
            eq = self._create_equipment(f'P04-{i:02d}')
            self.env['ts.maintenance.order'].create({
                'client_id': self.client.id,
                'equipment_id': eq.id,
                'service_type_id': self.service_type.id,
                'problem_description': f'Problema Dashboard {i}',
                'physical_condition': 'Sin daños.',
            })

        fields_list = list(self.env['ts.dashboard']._fields.keys())
        start = time.perf_counter()
        data = self.env['ts.dashboard'].default_get(fields_list)
        elapsed = time.perf_counter() - start

        self.assertGreaterEqual(data.get('total_orders', 0), 20)
        self.assertLess(elapsed, 3.0,
                        f"Carga del dashboard tardó {elapsed:.3f}s — Umbral SLA: 3s")

    # ── PERF-05: Cálculo de métricas de técnico ≤ 1s ─────────────────────
    def test_perf_05_technician_metrics_calculation(self):
        """PERF-05 | Rendimiento | Cálculo de métricas de técnico en < 1 segundo"""
        for i in range(10):
            eq = self._create_equipment(f'P05-{i:02d}')
            order = self.env['ts.maintenance.order'].create({
                'client_id': self.client.id,
                'equipment_id': eq.id,
                'service_type_id': self.service_type.id,
                'problem_description': f'Problema {i}',
                'physical_condition': 'Sin daños.',
                'technician_id': self.technician.id,
            })
            order.action_start_diagnosis()
            order.diagnosis = 'Falla encontrada.'
            order.action_start_repair()
            order.resolution = 'Reparado.'
            order.action_mark_ready()
            order.action_mark_delivered()
            order.action_close()

        start = time.perf_counter()
        self.technician._compute_order_metrics()
        elapsed = time.perf_counter() - start

        self.assertEqual(self.technician.completed_order_count, 10)
        self.assertLess(elapsed, 1.0,
                        f"Cálculo de métricas tardó {elapsed:.3f}s — Umbral SLA: 1s")


class TestSecurity(TransactionCase):
    """
    Pruebas de seguridad — Validación de controles de acceso y protección de datos.
    Verifica los mecanismos definidos en RNF-03 y RNF-04.
    """

    def setUp(self):
        super().setUp()
        self.client = self.env['res.partner'].create({'name': 'Cliente Security Test'})
        self.service_type = self.env['ts.service.type'].create({'name': 'Servicio Sec'})
        self.equipment = self.env['ts.equipment'].create({
            'name': 'Equipo Security',
            'equipment_type': 'laptop',
            'brand': 'HP',
            'model_name': 'Security Model',
            'serial_number': 'SN-SEC-001',
            'client_id': self.client.id,
        })

    # ── SEC-01: Log de auditoría inmutable — write (RF-15) ────────────────
    def test_sec_01_audit_log_write_immutable(self):
        """SEC-01 | Seguridad | write() en audit.log lanza AccessError"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'Prueba seguridad',
            'physical_condition': 'Sin daños.',
        })
        log = order.audit_log_ids[0]
        with self.assertRaises(AccessError):
            log.write({'description': 'Intento de manipulación del log'})

    # ── SEC-02: Log de auditoría inmutable — unlink (RF-15) ───────────────
    def test_sec_02_audit_log_unlink_immutable(self):
        """SEC-02 | Seguridad | unlink() en audit.log lanza AccessError"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'Prueba seguridad',
            'physical_condition': 'Sin daños.',
        })
        log = order.audit_log_ids[0]
        with self.assertRaises(AccessError):
            log.unlink()

    # ── SEC-03: Orden cerrada no modificable (RF-06) ───────────────────────
    def test_sec_03_closed_order_immutable(self):
        """SEC-03 | Seguridad | Estado cerrado protege la orden contra modificaciones"""
        tech = self.env['ts.technician'].create({
            'name': 'Técnico Sec',
            'employee_number': 'T-SEC-001',
        })
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id,
            'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id,
            'problem_description': 'Prueba seguridad',
            'physical_condition': 'Sin daños.',
            'technician_id': tech.id,
        })
        order.action_start_diagnosis()
        order.diagnosis = 'Diagnóstico.'
        order.action_start_repair()
        order.resolution = 'Reparado.'
        order.action_mark_ready()
        order.action_mark_delivered()
        order.action_close()

        with self.assertRaises(UserError):
            order.action_start_diagnosis()

    # ── SEC-04: Validación de datos de entrada (RF-01) ────────────────────
    def test_sec_04_input_validation_date_constraint(self):
        """SEC-04 | Seguridad | Fecha futura rechazada por @api.constrains"""
        with self.assertRaises(ValidationError):
            self.env['ts.maintenance.order'].create({
                'client_id': self.client.id,
                'equipment_id': self.equipment.id,
                'service_type_id': self.service_type.id,
                'problem_description': 'Test validación',
                'physical_condition': 'Sin daños.',
                'reception_date': date.today() + timedelta(days=10),
            })

    # ── SEC-05: Serial de equipo único (SQL constraint) (RF-11) ───────────
    def test_sec_05_serial_number_uniqueness_enforced(self):
        """
        SEC-05 | Seguridad | Serial duplicado bloqueado.
        Nota técnica: _sql_constraints genera psycopg2.errors.UniqueViolation a nivel BD
        (antes de que @api.constrains pueda convertirlo a ValidationError), por eso
        se usa assertRaises(Exception) que cubre ambos tipos de excepción.
        """
        with self.assertRaises(Exception):  # psycopg2.UniqueViolation o ValidationError
            self.env['ts.equipment'].create({
                'name': 'Copia fraudulenta',
                'equipment_type': 'laptop',
                'brand': 'Fake',
                'model_name': 'Clone',
                'serial_number': 'SN-SEC-001',  # ya existe en setUp
                'client_id': self.client.id,
            })
