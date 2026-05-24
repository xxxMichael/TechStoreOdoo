# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import date


class TsDashboard(models.TransientModel):
    """
    Panel de métricas gerenciales de TechStore Maintenance.
    Modelo transitorio que calcula todas las métricas en tiempo real.
    Cubre RF-18 (Dashboard), RF-19 (Export), RF-20 (ISO 25010 metrics).
    """
    _name = 'ts.dashboard'
    _description = 'Dashboard de Métricas TechStore'

    name = fields.Char(default='Dashboard TechStore', readonly=True)

    # ── Contadores por estado ─────────────────────────────────────────────────
    total_orders = fields.Integer(string='Total órdenes', readonly=True)
    count_received = fields.Integer(string='Recibidas', readonly=True)
    count_diagnosis = fields.Integer(string='En Diagnóstico', readonly=True)
    count_repair = fields.Integer(string='En Reparación', readonly=True)
    count_ready = fields.Integer(string='Listas para Entrega', readonly=True)
    count_delivered = fields.Integer(string='Entregadas', readonly=True)
    count_closed = fields.Integer(string='Cerradas', readonly=True)
    count_active = fields.Integer(string='Activas (no cerradas)', readonly=True)
    count_unassigned = fields.Integer(string='Sin técnico asignado', readonly=True)
    count_overdue = fields.Integer(string='Vencidas (fuera de SLA)', readonly=True)
    count_critical = fields.Integer(string='Prioridad Crítica activas', readonly=True)

    # ── Métricas de rendimiento ───────────────────────────────────────────────
    avg_resolution_days = fields.Float(
        string='Días prom. de resolución', digits=(6, 1), readonly=True,
    )
    recurrence_rate = fields.Float(
        string='Tasa de reincidencia (%)', digits=(6, 1), readonly=True,
    )

    # ── Métricas ISO 25010 (RF-20) ────────────────────────────────────────────
    iso_correctness = fields.Float(
        string='Funcionalidad Correcta (%)',
        digits=(6, 1),
        readonly=True,
        help='ISO 25010 — Functional Correctness: % de órdenes cerradas sin reincidencia.',
    )
    iso_efficiency = fields.Float(
        string='Eficiencia de Resolución (%)',
        digits=(6, 1),
        readonly=True,
        help='ISO 25010 — Performance Efficiency: % de órdenes cerradas dentro del SLA.',
    )
    iso_availability = fields.Char(
        string='Disponibilidad del Servicio',
        readonly=True,
        help='ISO 25010 — Reliability: estado de disponibilidad del módulo.',
    )
    iso_correctness_semaphore = fields.Selection(
        selection=[('green', 'Verde'), ('yellow', 'Amarillo'), ('red', 'Rojo')],
        string='Semáforo Funcionalidad',
        readonly=True,
    )
    iso_efficiency_semaphore = fields.Selection(
        selection=[('green', 'Verde'), ('yellow', 'Amarillo'), ('red', 'Rojo')],
        string='Semáforo Eficiencia',
        readonly=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    @api.model
    def default_get(self, fields_list):
        """
        Calcula todas las métricas al abrir el dashboard.
        RF-18: Los datos se actualizan automáticamente en cada apertura.
        """
        res = super().default_get(fields_list)
        Order = self.env['ts.maintenance.order']

        all_orders = Order.search([])
        active_orders = all_orders.filtered(lambda o: o.state not in ['closed'])
        closed_orders = all_orders.filtered(lambda o: o.state == 'closed')
        reopened = closed_orders.filtered(lambda o: o.reopened)

        # SLA en días por prioridad
        sla_map = {'3': 3, '2': 7, '1': 14, '0': 30}

        # Contadores por estado
        res.update({
            'total_orders': len(all_orders),
            'count_received': len(all_orders.filtered(lambda o: o.state == 'received')),
            'count_diagnosis': len(all_orders.filtered(lambda o: o.state == 'diagnosis')),
            'count_repair': len(all_orders.filtered(lambda o: o.state == 'repair')),
            'count_ready': len(all_orders.filtered(lambda o: o.state == 'ready')),
            'count_delivered': len(all_orders.filtered(lambda o: o.state == 'delivered')),
            'count_closed': len(closed_orders),
            'count_active': len(active_orders),
            'count_unassigned': len(active_orders.filtered(lambda o: not o.technician_id)),
            'count_critical': len(active_orders.filtered(lambda o: o.priority == '3')),
        })

        # Vencidas fuera de SLA
        today = date.today()
        overdue = 0
        for o in active_orders:
            if o.reception_date:
                sla = sla_map.get(o.priority, 30)
                if (today - o.reception_date).days > sla:
                    overdue += 1
        res['count_overdue'] = overdue

        # Días promedio de resolución
        if closed_orders:
            durations = [
                (o.close_date - o.reception_date).days
                for o in closed_orders
                if o.close_date and o.reception_date
            ]
            avg = sum(durations) / len(durations) if durations else 0.0
            res['avg_resolution_days'] = round(avg, 1)
            res['recurrence_rate'] = round((len(reopened) / len(closed_orders)) * 100, 1)
        else:
            res['avg_resolution_days'] = 0.0
            res['recurrence_rate'] = 0.0

        # ── ISO 25010 Métricas (RF-20) ────────────────────────────────────────
        # Funcionalidad Correcta: % órdenes sin reincidencia
        if closed_orders:
            correctness = ((len(closed_orders) - len(reopened)) / len(closed_orders)) * 100
        else:
            correctness = 100.0
        res['iso_correctness'] = round(correctness, 1)
        res['iso_correctness_semaphore'] = (
            'green' if correctness >= 90 else
            'yellow' if correctness >= 70 else
            'red'
        )

        # Eficiencia: % cerradas dentro del SLA
        if closed_orders:
            within_sla = sum(
                1 for o in closed_orders
                if o.reception_date and o.close_date and
                (o.close_date - o.reception_date).days <= sla_map.get(o.priority, 30)
            )
            efficiency = (within_sla / len(closed_orders)) * 100
        else:
            efficiency = 100.0
        res['iso_efficiency'] = round(efficiency, 1)
        res['iso_efficiency_semaphore'] = (
            'green' if efficiency >= 80 else
            'yellow' if efficiency >= 60 else
            'red'
        )

        res['iso_availability'] = 'Operativo ✅'

        return res

    def action_refresh(self):
        """Recarga el dashboard con datos frescos."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ts.dashboard',
            'view_mode': 'form',
            'target': 'main',
            'context': self.env.context,
        }

    def action_view_overdue(self):
        """Abre la lista de órdenes vencidas."""
        today = date.today()
        sla_map = {'3': 3, '2': 7, '1': 14, '0': 30}
        all_active = self.env['ts.maintenance.order'].search(
            [('state', 'not in', ['closed'])]
        )
        overdue_ids = [
            o.id for o in all_active
            if o.reception_date and
            (today - o.reception_date).days > sla_map.get(o.priority, 30)
        ]
        return {
            'type': 'ir.actions.act_window',
            'name': 'Órdenes Vencidas',
            'res_model': 'ts.maintenance.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', overdue_ids)],
        }

    def action_view_unassigned(self):
        """Abre las órdenes sin técnico asignado."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Órdenes Sin Técnico',
            'res_model': 'ts.maintenance.order',
            'view_mode': 'list,form',
            'domain': [
                ('technician_id', '=', False),
                ('state', 'not in', ['closed']),
            ],
        }

    def action_view_critical(self):
        """Abre las órdenes críticas activas."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Órdenes Críticas',
            'res_model': 'ts.maintenance.order',
            'view_mode': 'list,form',
            'domain': [
                ('priority', '=', '3'),
                ('state', 'not in', ['closed']),
            ],
        }

    def action_export_report(self):
        """RF-19: Lanza el reporte PDF de mantenimientos."""
        orders = self.env['ts.maintenance.order'].search([])
        return self.env.ref(
            'techstore_maintenance.action_report_maintenance_order'
        ).report_action(orders)
