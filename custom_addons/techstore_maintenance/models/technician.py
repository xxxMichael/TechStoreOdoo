# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class TsTechnician(models.Model):
    """
    Perfil extendido de técnico en TechStore.
    Registra especialidades, disponibilidad y métricas de rendimiento.
    Cubre los requisitos funcionales RF-07, RF-08, RF-09 y RF-10.
    """
    _name = 'ts.technician'
    _description = 'Técnico de TechStore'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # ─── Datos básicos ───────────────────────────────────────────────────────
    name = fields.Char(
        string='Nombre completo',
        required=True,
        tracking=True,
    )
    employee_number = fields.Char(
        string='Número de empleado',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: ('Nuevo'),
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Empleado (HR)',
        ondelete='set null',
        help='Vincula este técnico con el registro de empleado en el módulo HR.',
    )
    email = fields.Char(string='Correo electrónico')
    phone = fields.Char(string='Teléfono')

    # ─── Especialidades ───────────────────────────────────────────────────────
    # RF-07: Las especialidades son seleccionables y combinables
    specialty_hardware = fields.Boolean(string='Hardware')
    specialty_software = fields.Boolean(string='Software')
    specialty_networks = fields.Boolean(string='Redes')
    specialty_electronics = fields.Boolean(string='Electrónica')
    specialty_other = fields.Boolean(string='Otro')
    specialty_notes = fields.Char(
        string='Detalle de especialidad',
        help='Especifica otras especialidades si aplica.',
    )

    # ─── Estado y disponibilidad ─────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('active', 'Activo'),
            ('inactive', 'Inactivo'),
        ],
        string='Estado',
        default='active',
        required=True,
        tracking=True,
    )
    availability = fields.Selection(
        selection=[
            ('available', 'Disponible'),
            ('busy', 'Ocupado'),
            ('leave', 'En permiso'),
        ],
        string='Disponibilidad',
        default='available',
        tracking=True,
    )

    # ─── Órdenes asignadas ───────────────────────────────────────────────────
    # RF-08: Carga de trabajo por técnico
    order_ids = fields.One2many(
        comodel_name='ts.maintenance.order',
        inverse_name='technician_id',
        string='Órdenes asignadas',
    )
    active_order_count = fields.Integer(
        string='Órdenes activas',
        compute='_compute_order_metrics',
        store=True,
    )

    # ─── Métricas de rendimiento ─────────────────────────────────────────────
    # RF-09: Métricas individuales por técnico
    completed_order_count = fields.Integer(
        string='Órdenes completadas',
        compute='_compute_order_metrics',
        store=True,
    )
    avg_resolution_days = fields.Float(
        string='Días promedio de resolución',
        compute='_compute_order_metrics',
        store=True,
        digits=(6, 1),
    )
    recurrence_rate = fields.Float(
        string='Tasa de reincidencia (%)',
        compute='_compute_order_metrics',
        store=True,
        digits=(6, 1),
        help='Porcentaje de órdenes que fueron reabiertas respecto al total cerrado.',
    )

    # ─── Cómputo de métricas ─────────────────────────────────────────────────
    @api.depends('order_ids', 'order_ids.state', 'order_ids.reception_date',
                 'order_ids.close_date', 'order_ids.reopened')
    def _compute_order_metrics(self):
        """
        Calcula en tiempo real:
        - Órdenes activas (cualquier estado distinto de 'closed')
        - Órdenes completadas (estado 'closed')
        - Días promedio de resolución
        - Tasa de reincidencia
        """
        for tech in self:
            orders = tech.order_ids
            active = orders.filtered(lambda o: o.state not in ('closed',))
            closed = orders.filtered(lambda o: o.state == 'closed')
            reopened = closed.filtered(lambda o: o.reopened)

            tech.active_order_count = len(active)
            tech.completed_order_count = len(closed)

            if closed:
                durations = [
                    (o.close_date - o.reception_date).days
                    for o in closed
                    if o.close_date and o.reception_date
                ]
                tech.avg_resolution_days = sum(durations) / len(durations) if durations else 0.0
                tech.recurrence_rate = (len(reopened) / len(closed)) * 100
            else:
                tech.avg_resolution_days = 0.0
                tech.recurrence_rate = 0.0

    @api.model
    def create(self, vals):
        """
        Sobrescribe el método de creación para asignar un número de empleado secuencial.
        """
        if vals.get('employee_number', ('Nuevo')) == ('Nuevo'):
            vals['employee_number'] = self.env['ir.sequence'].next_by_code('ts.technician.employee_number') or ('Nuevo')
        return super(TsTechnician, self).create(vals)

    # ─── Acciones ─────────────────────────────────────────────────────────────
    def action_deactivate(self):
        """
        RF-10: Desactivar técnico.
        Si tiene órdenes activas, lanza el wizard de transferencia.
        """
        self.ensure_one()
        active_orders = self.order_ids.filtered(
            lambda o: o.state not in ('closed',)
        )
        if active_orders:
            raise UserError(
                f'El técnico "{self.name}" tiene {len(active_orders)} orden(es) activa(s). '
                'Debes reasignarlas antes de desactivarlo.\n\n'
                'Ve a cada orden activa y asigna un técnico de reemplazo.'
            )
        self.state = 'inactive'
        self.availability = 'busy'
        self.message_post(body='Técnico desactivado del sistema.')

    def action_activate(self):
        """Reactiva un técnico previamente desactivado."""
        self.ensure_one()
        self.state = 'active'
        self.availability = 'available'
        self.message_post(body='Técnico reactivado en el sistema.')

    def action_view_orders(self):
        """Abre las órdenes asignadas al técnico."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Órdenes de {self.name}',
            'res_model': 'ts.maintenance.order',
            'view_mode': 'list,form,kanban',
            'domain': [('technician_id', '=', self.id)],
            'context': {'default_technician_id': self.id},
        }

    _sql_constraints = [
        ('employee_number_unique', 'UNIQUE(employee_number)',
         'Ya existe un técnico con ese número de empleado.'),
    ]
