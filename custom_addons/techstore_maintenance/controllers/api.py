# -*- coding: utf-8 -*-
import json
from functools import wraps

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request, Response


class TechStoreApiController(http.Controller):
    RESOURCE_CONFIG = {
        'clients': {
            'model': 'res.partner',
            'fields': ['id', 'name', 'email', 'phone', 'mobile', 'is_company', 'active'],
            'writable_fields': ['name', 'email', 'phone', 'mobile', 'is_company', 'active'],
        },
        'service-types': {
            'model': 'ts.service.type',
            'fields': ['id', 'name', 'description', 'active', 'order_count'],
            'writable_fields': ['name', 'description', 'active'],
        },
        'technicians': {
            'model': 'ts.technician',
            'fields': [
                'id', 'name', 'employee_number', 'employee_id', 'email', 'phone',
                'specialty_hardware', 'specialty_software', 'specialty_networks',
                'specialty_electronics', 'specialty_other', 'specialty_notes',
                'state', 'availability', 'active_order_count',
                'completed_order_count', 'avg_resolution_days', 'recurrence_rate',
            ],
            'writable_fields': [
                'name', 'employee_number', 'employee_id', 'email', 'phone',
                'specialty_hardware', 'specialty_software', 'specialty_networks',
                'specialty_electronics', 'specialty_other', 'specialty_notes',
                'state', 'availability',
            ],
        },
        'equipment': {
            'model': 'ts.equipment',
            'fields': [
                'id', 'name', 'equipment_type', 'brand', 'model_name',
                'serial_number', 'current_state', 'notes', 'active', 'client_id',
                'order_count',
            ],
            'writable_fields': [
                'name', 'equipment_type', 'brand', 'model_name', 'serial_number',
                'current_state', 'notes', 'active', 'client_id',
            ],
        },
        'maintenance-orders': {
            'model': 'ts.maintenance.order',
            'fields': [
                'id', 'folio', 'client_id', 'equipment_id', 'service_type_id',
                'technician_id', 'state', 'priority', 'priority_kanban',
                'reception_date', 'close_date', 'days_open', 'problem_description',
                'physical_condition', 'diagnosis', 'work_done', 'parts_used',
                'resolution', 'delivery_confirmation', 'delivery_date', 'reopened',
            ],
            'writable_fields': [
                'client_id', 'equipment_id', 'service_type_id', 'technician_id',
                'priority', 'reception_date', 'problem_description',
                'physical_condition', 'diagnosis', 'work_done', 'parts_used',
                'resolution', 'delivery_confirmation', 'delivery_date', 'reopened',
            ],
        },
        'audit-logs': {
            'model': 'ts.audit.log',
            'fields': [
                'id', 'order_id', 'user_id', 'event_type', 'description',
                'event_date', 'create_date',
            ],
            'writable_fields': [],
        },
    }

    @http.route('/api/techstore/<string:resource>', type='http', auth='user', methods=['GET'], csrf=False)
    def list_resource(self, resource, **kwargs):
        config = self._get_resource_config(resource)
        limit = self._to_int(request.httprequest.args.get('limit'), 100)
        offset = self._to_int(request.httprequest.args.get('offset'), 0)
        domain = self._build_domain(config['model'])
        model = request.env[config['model']]
        records = model.search(domain, limit=limit, offset=offset)
        payload = {
            'count': model.search_count(domain),
            'items': [self._serialize_record(record, config) for record in records],
        }
        return self._json_response(payload)

    @http.route('/api/techstore/<string:resource>', type='http', auth='user', methods=['POST'], csrf=False)
    def create_resource(self, resource, **kwargs):
        config = self._get_resource_config(resource)
        self._ensure_writable_resource(config, operation='create')
        payload = self._get_json_payload()
        values = self._extract_values(payload, config)
        record = request.env[config['model']].create(values)
        return self._json_response(self._serialize_record(record, config), status=201)

    @http.route('/api/techstore/<string:resource>/<int:record_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_resource(self, resource, record_id, **kwargs):
        config = self._get_resource_config(resource)
        record = self._get_record(config, record_id)
        return self._json_response(self._serialize_record(record, config))

    @http.route('/api/techstore/<string:resource>/<int:record_id>', type='http', auth='user', methods=['PUT', 'PATCH'], csrf=False)
    def update_resource(self, resource, record_id, **kwargs):
        config = self._get_resource_config(resource)
        self._ensure_writable_resource(config, operation='update')
        record = self._get_record(config, record_id)
        payload = self._get_json_payload()

        if config['model'] == 'ts.maintenance.order':
            record._check_not_closed()
            technician_id = payload.pop('technician_id', None) if 'technician_id' in payload else None
            values = self._extract_values(payload, config)
            if values:
                record.write(values)
            if technician_id is not None:
                record.action_assign_technician(technician_id)
        else:
            values = self._extract_values(payload, config)
            record.write(values)

        return self._json_response(self._serialize_record(record, config))

    @http.route('/api/techstore/<string:resource>/<int:record_id>', type='http', auth='user', methods=['DELETE'], csrf=False)
    def delete_resource(self, resource, record_id, **kwargs):
        config = self._get_resource_config(resource)
        self._ensure_writable_resource(config, operation='delete')
        record = self._get_record(config, record_id)
        record.unlink()
        return self._json_response({'deleted': True, 'id': record_id})

    @http.route('/api/techstore/maintenance-orders/<int:record_id>/audit-logs', type='http', auth='user', methods=['GET'], csrf=False)
    def get_order_audit_logs(self, record_id, **kwargs):
        order_config = self._get_resource_config('maintenance-orders')
        log_config = self._get_resource_config('audit-logs')
        order = self._get_record(order_config, record_id)
        payload = {
            'order_id': order.id,
            'folio': order.folio,
            'items': [self._serialize_record(log, log_config) for log in order.audit_log_ids],
        }
        return self._json_response(payload)

    @http.route('/api/techstore/maintenance-orders/<int:record_id>/actions/<string:action_name>', type='http', auth='user', methods=['POST'], csrf=False)
    def order_action(self, record_id, action_name, **kwargs):
        config = self._get_resource_config('maintenance-orders')
        record = self._get_record(config, record_id)
        payload = self._get_json_payload(optional=True)
        action_map = {
            'assign-technician': lambda order: order.action_assign_technician(payload.get('technician_id')),
            'start-diagnosis': lambda order: order.action_start_diagnosis(),
            'start-repair': lambda order: order.action_start_repair(),
            'mark-ready': lambda order: order.action_mark_ready(),
            'mark-delivered': lambda order: order.action_mark_delivered(),
            'close': lambda order: order.action_close(),
        }
        if action_name not in action_map:
            return self._error_response('Accion no encontrada.', 404)
        if action_name == 'assign-technician' and not payload.get('technician_id'):
            return self._error_response('Debes enviar technician_id.', 400)
        action_map[action_name](record)
        return self._json_response(self._serialize_record(record, config))

    @http.route('/api/techstore/technicians/<int:record_id>/actions/<string:action_name>', type='http', auth='user', methods=['POST'], csrf=False)
    def technician_action(self, record_id, action_name, **kwargs):
        config = self._get_resource_config('technicians')
        record = self._get_record(config, record_id)
        action_map = {
            'activate': record.action_activate,
            'deactivate': record.action_deactivate,
        }
        if action_name not in action_map:
            return self._error_response('Accion no encontrada.', 404)
        action_map[action_name]()
        return self._json_response(self._serialize_record(record, config))

    @http.route('/api/techstore/dashboard', type='http', auth='user', methods=['GET'], csrf=False)
    def dashboard(self, **kwargs):
        dashboard_model = request.env['ts.dashboard']
        field_names = list(dashboard_model.fields_get().keys())
        payload = dashboard_model.default_get(field_names)
        return self._json_response(payload)

    def _get_resource_config(self, resource):
        config = self.RESOURCE_CONFIG.get(resource)
        if not config:
            raise MissingError('Recurso no encontrado.')
        return config

    def _get_record(self, config, record_id):
        record = request.env[config['model']].browse(record_id)
        if not record.exists():
            raise MissingError('Registro no encontrado.')
        return record

    def _get_json_payload(self, optional=False):
        raw_body = request.httprequest.data
        if not raw_body:
            return {} if optional else {}
        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValidationError('El cuerpo de la solicitud debe ser JSON valido.')
        if not isinstance(payload, dict):
            raise ValidationError('El cuerpo JSON debe ser un objeto.')
        return payload

    def _extract_values(self, payload, config):
        values = {}
        for field_name in config['writable_fields']:
            if field_name in payload:
                values[field_name] = payload[field_name]
        return values

    def _ensure_writable_resource(self, config, operation):
        if config['writable_fields'] or config['model'] != 'ts.audit.log':
            return
        raise UserError('El recurso no permite operaciones de %s.' % operation)

    def _build_domain(self, model_name):
        domain = []
        params = request.httprequest.args
        model = request.env[model_name]
        for key, value in params.items():
            if key in ('limit', 'offset') or key not in model._fields:
                continue
            field = model._fields[key]
            if field.type == 'many2one':
                domain.append((key, '=', self._to_int(value, 0)))
            elif field.type in ('integer', 'float', 'monetary'):
                domain.append((key, '=', float(value) if field.type in ('float', 'monetary') else self._to_int(value, 0)))
            elif field.type == 'boolean':
                domain.append((key, '=', value.lower() in ('1', 'true', 'yes')))
            else:
                domain.append((key, '=', value))
        return domain

    def _serialize_record(self, record, config):
        data = record.read(config['fields'])[0]
        for key, value in list(data.items()):
            if isinstance(value, (tuple, list)) and len(value) == 2 and isinstance(value[0], int):
                data[key] = {'id': value[0], 'name': value[1]}
        for field_name in config['fields']:
            field = record._fields.get(field_name)
            if field and field.type == 'selection':
                data['%s_label' % field_name] = dict(field.selection).get(record[field_name])
        return data

    def _json_response(self, payload, status=200):
        return Response(
            json.dumps(payload, ensure_ascii=False, default=str),
            status=status,
            content_type='application/json; charset=utf-8',
        )

    def _error_response(self, message, status):
        return self._json_response({'error': message}, status=status)

    def _to_int(self, value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _handle_api_errors(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except AccessError as error:
                return self._error_response(str(error), 403)
            except MissingError as error:
                return self._error_response(str(error), 404)
            except (UserError, ValidationError) as error:
                return self._error_response(str(error), 400)
            except Exception as error:
                return self._error_response(str(error), 500)
        wrapper.routing = getattr(func, 'routing', None)
        return wrapper


for route_name in (
    'list_resource',
    'create_resource',
    'get_resource',
    'update_resource',
    'delete_resource',
    'get_order_audit_logs',
    'order_action',
    'technician_action',
    'dashboard',
):
    setattr(
        TechStoreApiController,
        route_name,
        TechStoreApiController._handle_api_errors(getattr(TechStoreApiController, route_name)),
    )
