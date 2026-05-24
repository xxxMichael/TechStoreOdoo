# -*- coding: utf-8 -*-
from odoo import models, fields


class TsServiceType(models.Model):
    """
    Catálogo de tipos de servicio disponibles en TechStore.
    Ejemplos: Diagnóstico, Reparación de hardware, Actualización de software,
              Limpieza, Instalación de red, etc.
    """
    _name = 'ts.service.type'
    _description = 'Tipo de Servicio Técnico'
    _order = 'name'

    name = fields.Char(
        string='Nombre del Servicio',
        required=True,
        translate=True,
    )
    description = fields.Text(
        string='Descripción',
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
    )

    # Relación inversa: cuántas órdenes usan este tipo de servicio
    order_ids = fields.One2many(
        comodel_name='ts.maintenance.order',
        inverse_name='service_type_id',
        string='Órdenes asociadas',
    )
    order_count = fields.Integer(
        string='Número de Órdenes',
        compute='_compute_order_count',
    )

    def _compute_order_count(self):
        for record in self:
            record.order_count = len(record.order_ids)

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Ya existe un tipo de servicio con ese nombre.'),
    ]
