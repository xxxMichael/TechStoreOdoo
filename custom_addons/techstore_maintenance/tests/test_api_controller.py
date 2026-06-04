# -*- coding: utf-8 -*-
import json
from datetime import date
from odoo.tests.common import HttpCase

class TechStoreHttpCase(HttpCase):
    """Clase base para pruebas de API de TechStore con soporte REST nativo."""
    
    def setUp(self):
        super().setUp()
        self.authenticate('admin', 'admin')

    def _api_request(self, method, path, data=None):
        """Realiza peticiones RESTful usando el opener de Odoo."""
        url = f"{self.base_url()}{path}"
        headers = {'Content-Type': 'application/json'}
        payload = json.dumps(data) if data is not None else None
        # self.opener es una instancia de requests.Session
        return self.opener.request(method, url, data=payload, headers=headers)

class TestApiCrud(TechStoreHttpCase):
    """AC: API Controller — Endpoints CRUD genéricos"""

    def setUp(self):
        super().setUp()
        self.client_partner = self.env['res.partner'].create({'name': 'Cliente HTTP Test', 'is_company': True})
        self.service_type = self.env['ts.service.type'].create({'name': 'Servicio HTTP Test'})
        self.technician = self.env['ts.technician'].create({'name': 'Tecnico HTTP', 'employee_number': 'T-HTTP-001'})
        self.equipment = self.env['ts.equipment'].create({
            'name': 'Equipo HTTP Test', 'equipment_type': 'laptop', 'brand': 'HP',
            'model_name': 'ProBook', 'serial_number': 'SN-HTTP-001', 'client_id': self.client_partner.id,
        })

    def test_ac_01_dashboard_returns_metrics(self):
        """AC-01 | GET /api/techstore/dashboard devuelve metricas"""
        resp = self._api_request('GET', '/api/techstore/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('total_orders', resp.json())

    def test_ac_02_list_orders_returns_paginated_collection(self):
        """AC-02 | GET /api/techstore/maintenance-orders devuelve coleccion"""
        resp = self._api_request('GET', '/api/techstore/maintenance-orders?limit=10')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('items', resp.json())

    def test_ac_03_create_order_returns_201_with_received_state(self):
        """AC-03 | POST /api/techstore/maintenance-orders crea registro"""
        payload = {
            'client_id': self.client_partner.id, 'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id, 'priority': '1',
            'problem_description': 'Test create', 'physical_condition': 'Good',
        }
        resp = self._api_request('POST', '/api/techstore/maintenance-orders', data=payload)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json().get('state'), 'received')

    def test_ac_04_get_single_order_by_id(self):
        """AC-04 | GET /api/techstore/maintenance-orders/{id}"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client_partner.id, 'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id, 'problem_description': 'P', 'physical_condition': 'C',
        })
        resp = self._api_request('GET', f'/api/techstore/maintenance-orders/{order.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('id'), order.id)

    def test_ac_05_get_nonexistent_record_returns_404(self):
        """AC-05 | GET registro inexistente -> 404"""
        resp = self._api_request('GET', '/api/techstore/maintenance-orders/999999')
        self.assertEqual(resp.status_code, 404)

    def test_ac_06_patch_order_updates_fields(self):
        """AC-06 | PATCH actualiza campos parciales"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client_partner.id, 'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id, 'problem_description': 'Old', 'physical_condition': 'C',
        })
        resp = self._api_request('PATCH', f'/api/techstore/maintenance-orders/{order.id}', data={'problem_description': 'New'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get('problem_description'), 'New')

    def test_ac_07_delete_equipment_returns_deleted_true(self):
        """AC-07 | DELETE /api/techstore/equipment/{id}"""
        eq = self.env['ts.equipment'].create({
            'name': 'Del', 'equipment_type': 'laptop', 'brand': 'B', 'model_name': 'M', 
            'serial_number': 'SN-DEL', 'client_id': self.client_partner.id
        })
        resp = self._api_request('DELETE', f'/api/techstore/equipment/{eq.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(eq.exists())

    def test_ac_08_list_technicians_includes_metrics(self):
        """AC-08 | GET /api/techstore/technicians incluye metricas"""
        resp = self._api_request('GET', '/api/techstore/technicians')
        self.assertEqual(resp.status_code, 200)
        items = resp.json().get('items', [])
        self.assertTrue(any(t['id'] == self.technician.id for t in items))

    def test_ac_09_list_equipment_returns_serial_number(self):
        """AC-09 | GET /api/techstore/equipment incluye serial_number"""
        resp = self._api_request('GET', '/api/techstore/equipment')
        self.assertEqual(resp.status_code, 200)
        items = resp.json().get('items', [])
        self.assertTrue(any(e['serial_number'] == 'SN-HTTP-001' for e in items))

    def test_ac_10_audit_logs_endpoint_returns_items(self):
        """AC-10 | GET /api/techstore/maintenance-orders/{id}/audit-logs"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.client_partner.id, 'equipment_id': self.equipment.id,
            'service_type_id': self.service_type.id, 'problem_description': 'P', 'physical_condition': 'C',
        })
        resp = self._api_request('GET', f'/api/techstore/maintenance-orders/{order.id}/audit-logs')
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(resp.json().get('items', [])), 0)

class TestApiOrderActions(TechStoreHttpCase):
    """AA: API Actions — Ciclo de vida de la orden"""

    def setUp(self):
        super().setUp()
        self.client = self.env['res.partner'].create({'name': 'C'})
        self.service = self.env['ts.service.type'].create({'name': 'S'})
        self.tech = self.env['ts.technician'].create({'name': 'T', 'employee_number': 'T-AA'})
        self.eq = self.env['ts.equipment'].create({
            'name': 'E', 'equipment_type': 'laptop', 'brand': 'B', 'model_name': 'M', 
            'serial_number': 'SN-AA', 'client_id': self.client.id
        })
        self.order = self.env['ts.maintenance.order'].create({
            'client_id': self.client.id, 'equipment_id': self.eq.id,
            'service_type_id': self.service.id, 'problem_description': 'P', 'physical_condition': 'C',
        })

    def _post_action(self, action, data=None):
        return self._api_request('POST', f'/api/techstore/maintenance-orders/{self.order.id}/actions/{action}', data=data)

    def test_aa_01_assign_technician_returns_200(self):
        """AA-01 | Asignar tecnico via API"""
        resp = self._post_action('assign-technician', {'technician_id': self.tech.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.order.technician_id.id, self.tech.id)

    def test_aa_02_assign_technician_without_id_returns_400(self):
        """AA-02 | Asignar sin ID -> 400"""
        resp = self._post_action('assign-technician', {})
        self.assertEqual(resp.status_code, 400)

    def test_aa_03_start_diagnosis_without_technician_returns_400(self):
        """AA-03 | Diagnostico sin tecnico -> 400"""
        resp = self._post_action('start-diagnosis')
        self.assertEqual(resp.status_code, 400)

    def test_aa_04_full_lifecycle_via_api(self):
        """AA-04 | Flujo completo via API"""
        self._post_action('assign-technician', {'technician_id': self.tech.id})
        self._post_action('start-diagnosis')
        self._api_request('PATCH', f'/api/techstore/maintenance-orders/{self.order.id}', data={'diagnosis': 'D'})
        self._post_action('start-repair')
        self._api_request('PATCH', f'/api/techstore/maintenance-orders/{self.order.id}', data={'resolution': 'R'})
        self._post_action('mark-ready')
        self._post_action('mark-delivered')
        resp = self._post_action('close')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.order.state, 'closed')

    def test_aa_05_action_on_closed_order_returns_400(self):
        """AA-05 | Accion en cerrada -> 400"""
        self.order.technician_id = self.tech
        self.order.action_start_diagnosis()
        self.order.diagnosis = 'D'
        self.order.action_start_repair()
        self.order.resolution = 'R'
        self.order.action_mark_ready()
        self.order.action_mark_delivered()
        self.order.action_close()
        resp = self._post_action('start-diagnosis')
        self.assertEqual(resp.status_code, 400)

    def test_aa_06_unknown_action_returns_404(self):
        """AA-06 | Accion inexistente -> 404"""
        resp = self._post_action('fake-action')
        self.assertEqual(resp.status_code, 404)

    def test_aa_07_technician_deactivate_and_activate_actions(self):
        """AA-07 | Activar/Desactivar tecnico via API"""
        resp = self._api_request('POST', f'/api/techstore/technicians/{self.tech.id}/actions/deactivate')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.tech.state, 'inactive')
        resp = self._api_request('POST', f'/api/techstore/technicians/{self.tech.id}/actions/activate')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.tech.state, 'active')

class TestApiSecurity(TechStoreHttpCase):
    """AS: API Security — Controles de acceso y validación"""

    def test_as_01_malformed_json_returns_400(self):
        """AS-01 | JSON malformado -> 400"""
        url = f"{self.base_url()}/api/techstore/clients"
        resp = self.opener.post(url, data="{bad", headers={'Content-Type': 'application/json'})
        self.assertEqual(resp.status_code, 400)

    def test_as_02_unknown_resource_returns_404(self):
        """AS-02 | Recurso falso -> 404"""
        resp = self._api_request('GET', '/api/techstore/ghost')
        self.assertEqual(resp.status_code, 404)

    def test_as_03_direct_audit_log_creation_blocked(self):
        """AS-03 | Crear log directo bloqueado"""
        resp = self._api_request('POST', '/api/techstore/audit-logs', data={'description': 'X'})
        self.assertEqual(resp.status_code, 400)

    def test_as_04_undefined_order_action_returns_404(self):
        """AS-04 | Accion nula -> 404"""
        resp = self._api_request('POST', '/api/techstore/maintenance-orders/1/actions/none')
        self.assertEqual(resp.status_code, 404)

    def test_as_05_response_content_type_is_json(self):
        """AS-05 | Content-Type JSON"""
        resp = self._api_request('GET', '/api/techstore/dashboard')
        self.assertIn('application/json', resp.headers.get('Content-Type'))

    def test_as_06_audit_log_patch_blocked(self):
        """AS-06 | PATCH log bloqueado"""
        order = self.env['ts.maintenance.order'].create({
            'client_id': self.env['res.partner'].create({'name': 'T'}).id,
            'equipment_id': self.env['ts.equipment'].create({
                'name': 'E', 'equipment_type': 'laptop', 'brand': 'B', 'model_name': 'M', 
                'serial_number': 'SN-LOG', 'client_id': 1
            }).id,
            'service_type_id': self.env['ts.service.type'].create({'name': 'S'}).id,
            'problem_description': 'P', 'physical_condition': 'C',
        })
        log = order.audit_log_ids[0]
        resp = self._api_request('PATCH', f'/api/techstore/audit-logs/{log.id}', data={'description': 'X'})
        self.assertEqual(resp.status_code, 400)
