# -*- coding: utf-8 -*-
from odoo import models, fields


class TsAuditLog(models.Model):
    """
    Registro inmutable de cambios realizados sobre órdenes de mantenimiento.
    Cubre el requisito funcional RF-15.

    IMPORTANTE: Este modelo NO debe permitir write() ni unlink() por ningún usuario.
    La restricción se gestiona a través de los permisos en ir.model.access.csv
    (solo create y read; sin update ni delete para ningún grupo).
    """
    _name = 'ts.audit.log'
    _description = 'Log de Auditoría de Órdenes'
    _order = 'create_date desc'
    _log_access = True   # Mantiene create_date, write_date automáticos

    # Orden de mantenimiento afectada
    order_id = fields.Many2one(
        comodel_name='ts.maintenance.order',
        string='Orden de mantenimiento',
        required=True,
        ondelete='cascade',
        readonly=True,
        index=True,
    )

    # Usuario que realizó el cambio
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Usuario',
        required=True,
        readonly=True,
        default=lambda self: self.env.uid,
    )

    # Tipo de evento registrado
    event_type = fields.Char(
        string='Tipo de evento',
        required=True,
        readonly=True,
        help='Ej: "Cambio de estado", "Cambio de técnico", "Orden creada".',
    )

    # Descripción detallada del cambio
    description = fields.Text(
        string='Descripción del cambio',
        required=True,
        readonly=True,
    )

    # Fecha y hora del cambio (tomada del create_date del ORM)
    event_date = fields.Datetime(
        string='Fecha y hora',
        default=fields.Datetime.now,
        readonly=True,
    )

    def write(self, vals):
        """Bloquea cualquier modificación posterior al registro."""
        raise models.AccessError(
            'Los registros del log de auditoría son inmutables y no pueden modificarse.'
        )

    def unlink(self):
        """Bloquea la eliminación de registros de auditoría."""
        raise models.AccessError(
            'Los registros del log de auditoría son inmutables y no pueden eliminarse.'
        )
