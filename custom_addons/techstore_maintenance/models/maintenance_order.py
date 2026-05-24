# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import date


class TsMaintenanceOrder(models.Model):
    """
    Orden de mantenimiento técnico — entidad central del sistema TechStore.

    Cubre los requisitos funcionales:
      RF-01: Crear orden de mantenimiento
      RF-02: Asignar técnico a una orden
      RF-03: Actualizar el estado de una orden
      RF-04: Establecer y modificar la prioridad
      RF-05: Registrar diagnóstico y resolución
      RF-06: Cerrar y archivar una orden
    """
    _name = 'ts.maintenance.order'
    _description = 'Orden de Mantenimiento TechStore'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, reception_date desc'
    _rec_name = 'folio'

    # ─────────────────────────────────────────────────────────────────────────
    # CAMPOS DE IDENTIFICACIÓN
    # ─────────────────────────────────────────────────────────────────────────

    # RF-01: Folio único autogenerado
    folio = fields.Char(
        string='Folio',
        required=True,
        readonly=True,
        default='Nuevo',
        copy=False,
        tracking=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # RELACIONES PRINCIPALES
    # ─────────────────────────────────────────────────────────────────────────

    # RF-01: Cliente asociado a la orden
    client_id = fields.Many2one(
        comodel_name='res.partner',
        string='Cliente',
        required=True,
        ondelete='restrict',
        tracking=True,
    )

    # RF-01: Equipo en mantenimiento
    equipment_id = fields.Many2one(
        comodel_name='ts.equipment',
        string='Equipo',
        required=True,
        ondelete='restrict',
        tracking=True,
        domain="[('client_id', '=', client_id)]",
    )

    # RF-01: Tipo de servicio
    service_type_id = fields.Many2one(
        comodel_name='ts.service.type',
        string='Tipo de servicio',
        required=True,
        ondelete='restrict',
    )

    # RF-02: Técnico asignado
    technician_id = fields.Many2one(
        comodel_name='ts.technician',
        string='Técnico asignado',
        ondelete='set null',
        tracking=True,
        domain=[('state', '=', 'active')],
    )

    # ─────────────────────────────────────────────────────────────────────────
    # ESTADO Y PRIORIDAD
    # ─────────────────────────────────────────────────────────────────────────

    # RF-03: Ciclo de vida de la orden
    state = fields.Selection(
        selection=[
            ('received', 'Recibido'),
            ('diagnosis', 'En Diagnóstico'),
            ('repair', 'En Reparación'),
            ('ready', 'Listo para Entrega'),
            ('delivered', 'Entregado'),
            ('closed', 'Cerrado'),
        ],
        string='Estado',
        default='received',
        required=True,
        tracking=True,
        group_expand='_expand_states',
    )

    # RF-04: Nivel de prioridad
    priority = fields.Selection(
        selection=[
            ('0', 'Baja'),
            ('1', 'Media'),
            ('2', 'Alta'),
            ('3', 'Crítica'),
        ],
        string='Prioridad',
        default='0',
        required=True,
        tracking=True,
    )
    # Campo auxiliar para el widget kanban (estrella)
    priority_kanban = fields.Boolean(
        string='Prioridad alta',
        compute='_compute_priority_kanban',
        store=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # FECHAS
    # ─────────────────────────────────────────────────────────────────────────

    # RF-01: Fecha de recepción
    reception_date = fields.Date(
        string='Fecha de recepción',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    # RF-03: Fecha de cierre
    close_date = fields.Date(
        string='Fecha de cierre',
        readonly=True,
        tracking=True,
    )
    # Días transcurridos desde la recepción
    days_open = fields.Integer(
        string='Días abierta',
        compute='_compute_days_open',
        store=False,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # DESCRIPCIÓN DEL PROBLEMA Y DIAGNÓSTICO
    # ─────────────────────────────────────────────────────────────────────────

    # RF-01: Descripción del problema reportado por el cliente
    problem_description = fields.Text(
        string='Problema reportado',
        required=True,
    )

    # RF-13: Estado físico del equipo al ingreso (obligatorio)
    physical_condition = fields.Text(
        string='Estado físico al ingreso',
        required=True,
        help='Describe el estado físico del equipo: daños visibles, accesorios incluidos, etc.',
    )

    # RF-05: Diagnóstico técnico
    diagnosis = fields.Text(
        string='Diagnóstico técnico',
        tracking=True,
    )

    # RF-05: Trabajos realizados y repuestos utilizados
    work_done = fields.Text(
        string='Trabajos realizados',
    )
    parts_used = fields.Text(
        string='Repuestos utilizados',
    )

    # RF-05: Solución aplicada
    resolution = fields.Text(
        string='Solución aplicada',
        tracking=True,
    )

    # RF-06: Confirmación de entrega
    delivery_confirmation = fields.Text(
        string='Confirmación de entrega',
    )
    delivery_date = fields.Date(
        string='Fecha de entrega',
    )

    # ─────────────────────────────────────────────────────────────────────────
    # CAMPOS DE CONTROL Y MÉTRICAS
    # ─────────────────────────────────────────────────────────────────────────

    # RF-09: Indica si la orden fue reabierta (para calcular tasa de reincidencia)
    reopened = fields.Boolean(
        string='Reabierta',
        default=False,
        tracking=True,
        help='Marcada automáticamente si la orden se reabre tras ser cerrada.',
    )

    # Log de auditoría interno (RF-15)
    audit_log_ids = fields.One2many(
        comodel_name='ts.audit.log',
        inverse_name='order_id',
        string='Log de auditoría',
        readonly=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTODOS ORM
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def create(self, vals):
        """RF-01: Genera folio único automático al crear la orden."""
        if vals.get('folio', 'Nuevo') == 'Nuevo':
            vals['folio'] = self.env['ir.sequence'].next_by_code(
                'ts.maintenance.order'
            ) or 'Nuevo'
        order = super().create(vals)
        # Registra la creación en el log de auditoría
        order._log_audit_event('Orden creada', f'Estado inicial: Recibido | Prioridad: {dict(order._fields["priority"].selection).get(order.priority)}')
        return order

    # ─────────────────────────────────────────────────────────────────────────
    # CÓMPUTOS
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('priority')
    def _compute_priority_kanban(self):
        for rec in self:
            rec.priority_kanban = rec.priority in ('2', '3')

    @api.depends('reception_date', 'close_date', 'state')
    def _compute_days_open(self):
        today = date.today()
        for rec in self:
            if rec.reception_date:
                end = rec.close_date or today
                rec.days_open = (end - rec.reception_date).days
            else:
                rec.days_open = 0

    # ─────────────────────────────────────────────────────────────────────────
    # ONCHANGE
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('client_id')
    def _onchange_client_id(self):
        """Limpia el equipo si se cambia el cliente."""
        if self.equipment_id and self.equipment_id.client_id != self.client_id:
            self.equipment_id = False
        return {'domain': {'equipment_id': [('client_id', '=', self.client_id.id)]}}

    # ─────────────────────────────────────────────────────────────────────────
    # TRANSICIONES DE ESTADO (RF-03)
    # ─────────────────────────────────────────────────────────────────────────

    def action_start_diagnosis(self):
        """Recibido → En Diagnóstico"""
        self._check_not_closed()
        for rec in self:
            if rec.state != 'received':
                raise UserError('Solo se puede iniciar diagnóstico desde el estado "Recibido".')
            if not rec.technician_id:
                raise UserError('Debes asignar un técnico antes de iniciar el diagnóstico.')
            rec.state = 'diagnosis'
            rec._log_audit_event('Cambio de estado', 'Recibido → En Diagnóstico')

    def action_start_repair(self):
        """En Diagnóstico → En Reparación"""
        self._check_not_closed()
        for rec in self:
            if rec.state != 'diagnosis':
                raise UserError('Solo se puede iniciar reparación desde "En Diagnóstico".')
            if not rec.diagnosis:
                raise UserError('Debes registrar el diagnóstico antes de pasar a reparación.')
            rec.state = 'repair'
            rec._log_audit_event('Cambio de estado', 'En Diagnóstico → En Reparación')

    def action_mark_ready(self):
        """En Reparación → Listo para Entrega"""
        self._check_not_closed()
        for rec in self:
            if rec.state != 'repair':
                raise UserError('La orden debe estar en "En Reparación" para marcarla como lista.')
            if not rec.resolution:
                raise UserError('Debes registrar la solución aplicada antes de marcar como listo.')
            rec.state = 'ready'
            rec._log_audit_event('Cambio de estado', 'En Reparación → Listo para Entrega')
            # RF-16: Notifica al cliente
            rec._notify_client_ready()

    def action_mark_delivered(self):
        """Listo para Entrega → Entregado"""
        self._check_not_closed()
        for rec in self:
            if rec.state != 'ready':
                raise UserError('La orden debe estar "Lista para Entrega" para marcarla como entregada.')
            rec.state = 'delivered'
            rec.delivery_date = date.today()
            rec._log_audit_event('Cambio de estado', 'Listo para Entrega → Entregado')

    def action_close(self):
        """Entregado → Cerrado (RF-06)"""
        self._check_not_closed()
        for rec in self:
            if rec.state != 'delivered':
                raise UserError('Solo se puede cerrar una orden que esté en estado "Entregado".')
            rec.state = 'closed'
            rec.close_date = date.today()
            rec._log_audit_event('Orden cerrada', f'Fecha de cierre: {rec.close_date}')
            # Actualiza métricas del técnico
            if rec.technician_id:
                rec.technician_id._compute_order_metrics()

    def action_assign_technician(self, technician_id):
        """RF-02: Asigna técnico con notificación automática."""
        self._check_not_closed()
        for rec in self:
            old_tech = rec.technician_id.name if rec.technician_id else 'Sin asignar'
            rec.technician_id = technician_id
            new_tech = rec.technician_id.name
            rec._log_audit_event(
                'Cambio de técnico',
                f'Técnico anterior: {old_tech} → Nuevo técnico: {new_tech}'
            )

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS INTERNOS
    # ─────────────────────────────────────────────────────────────────────────

    def _check_not_closed(self):
        """RF-06: Las órdenes cerradas no pueden modificarse."""
        for rec in self:
            if rec.state == 'closed':
                raise UserError(
                    f'La orden {rec.folio} está cerrada y no puede modificarse.'
                )

    def _log_audit_event(self, event_type, description):
        """RF-15: Registra un evento en el log de auditoría."""
        self.env['ts.audit.log'].create({
            'order_id': self.id,
            'user_id': self.env.uid,
            'event_type': event_type,
            'description': description,
        })

    def _notify_client_ready(self):
        """RF-16: Notificación interna cuando la orden está lista para entrega."""
        self.message_post(
            body=(
                f'✅ La orden <b>{self.folio}</b> está <b>Lista para Entrega</b>.<br/>'
                f'Equipo: {self.equipment_id.brand} {self.equipment_id.model_name}<br/>'
                f'Cliente: {self.client_id.name}'
            ),
            subject=f'Orden {self.folio} — Lista para Entrega',
            message_type='notification',
        )

    # ─────────────────────────────────────────────────────────────────────────
    # EXPANSIÓN DE ESTADOS PARA KANBAN (RF-14)
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def _expand_states(self, states, domain, order):
        """Muestra todas las columnas del kanban aunque estén vacías."""
        return [key for key, _ in self._fields['state'].selection]

    # ─────────────────────────────────────────────────────────────────────────
    # RESTRICCIONES
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('reception_date')
    def _check_reception_date(self):
        for rec in self:
            if rec.reception_date and rec.reception_date > date.today():
                raise ValidationError('La fecha de recepción no puede ser futura.')
