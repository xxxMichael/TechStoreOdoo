# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TsEquipment(models.Model):
    """
    Equipo tecnológico registrado por cliente en TechStore.
    Cubre los requisitos funcionales RF-11, RF-12 y RF-13.
    """
    _name = 'ts.equipment'
    _description = 'Equipo Tecnológico de Cliente'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'client_id, name'

    # ─── Datos del equipo ─────────────────────────────────────────────────────
    name = fields.Char(
        string='Nombre / Identificador',
        required=True,
        help='Nombre descriptivo del equipo. Ej: "Laptop HP de Gerencia".',
    )
    # RF-11: Tipo de equipo
    equipment_type = fields.Selection(
        selection=[
            ('laptop', 'Laptop'),
            ('desktop', 'Desktop / Torre'),
            ('printer', 'Impresora'),
            ('server', 'Servidor'),
            ('tablet', 'Tablet'),
            ('phone', 'Teléfono / Celular'),
            ('network', 'Equipo de Red'),
            ('other', 'Otro'),
        ],
        string='Tipo de equipo',
        required=True,
        tracking=True,
    )
    brand = fields.Char(
        string='Marca',
        required=True,
    )
    model_name = fields.Char(
        string='Modelo',
        required=True,
    )
    # RF-11: Número de serie único
    serial_number = fields.Char(
        string='Número de serie',
        required=True,
        copy=False,
        tracking=True,
    )
    current_state = fields.Selection(
        selection=[
            ('operational', 'Operativo'),
            ('faulty', 'Con falla'),
            ('under_maintenance', 'En mantenimiento'),
            ('retired', 'Dado de baja'),
        ],
        string='Estado actual',
        default='operational',
        tracking=True,
    )
    notes = fields.Text(
        string='Observaciones generales',
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
    )

    # ─── Relaciones ───────────────────────────────────────────────────────────
    # RF-11: Cada equipo vinculado a un cliente específico
    client_id = fields.Many2one(
        comodel_name='res.partner',
        string='Cliente propietario',
        required=True,
        ondelete='restrict',
        tracking=True,
        domain=[('is_company', 'in', [True, False])],
    )

    # RF-12: Historial de órdenes de mantenimiento por equipo
    order_ids = fields.One2many(
        comodel_name='ts.maintenance.order',
        inverse_name='equipment_id',
        string='Historial de mantenimientos',
    )
    order_count = fields.Integer(
        string='Total de mantenimientos',
        compute='_compute_order_count',
    )

    # ─── Cómputos ─────────────────────────────────────────────────────────────
    @api.depends('order_ids')
    def _compute_order_count(self):
        for record in self:
            record.order_count = len(record.order_ids)

    # ─── Restricciones ───────────────────────────────────────────────────────
    @api.constrains('serial_number')
    def _check_serial_number_unique(self):
        """RF-11: El número de serie debe ser único en todo el sistema."""
        for record in self:
            duplicate = self.search([
                ('serial_number', '=', record.serial_number),
                ('id', '!=', record.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    f'Ya existe un equipo registrado con el número de serie '
                    f'"{record.serial_number}" (Equipo: {duplicate.name}, '
                    f'Cliente: {duplicate.client_id.name}).'
                )

    # ─── Acciones ─────────────────────────────────────────────────────────────
    def action_view_maintenance_history(self):
        """RF-12: Abre el historial completo de mantenimientos del equipo."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Historial — {self.name}',
            'res_model': 'ts.maintenance.order',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
            'context': {
                'default_equipment_id': self.id,
                'default_client_id': self.client_id.id,
                'search_default_group_by_state': 1,
            },
        }

    _sql_constraints = [
        ('serial_number_unique', 'UNIQUE(serial_number)',
         'El número de serie ya está registrado en el sistema.'),
    ]

    def name_get(self):
        result = []
        for rec in self:
            display = f'[{rec.serial_number}] {rec.brand} {rec.model_name} — {rec.client_id.name}'
            result.append((rec.id, display))
        return result
