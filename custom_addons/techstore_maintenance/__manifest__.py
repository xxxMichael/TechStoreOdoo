# -*- coding: utf-8 -*-
{
    'name': 'TechStore Maintenance',
    'version': '16.0.1.0.0',
    'summary': 'Sistema de Gestión de Mantenimientos Técnicos — TechStore',
    'description': """
        Módulo para la gestión integral de órdenes de mantenimiento técnico,
        equipos de clientes, técnicos especializados y métricas de calidad
        alineadas con ISO/IEC 25010.

        Funcionalidades principales:
        - Gestión de órdenes de mantenimiento con ciclo de vida completo
        - Registro y seguimiento de equipos tecnológicos por cliente
        - Gestión de técnicos con especialidades y carga de trabajo
        - Tablero kanban de órdenes activas
        - Log de auditoría inmutable
        - Dashboard de métricas de calidad y rendimiento
    """,
    'author': 'TechStore — Proyecto Integrador GCS',
    'category': 'Services/Maintenance',
    'license': 'LGPL-3',

    'depends': [
        'base',
        'mail',
        'hr',
    ],

    'data': [
        # Seguridad — se carga primero
        'security/security.xml',
        'security/ir.model.access.csv',

        # Datos iniciales de catálogo
        'data/service_type_data.xml',

        # Vistas — orden importante: primero modelos base, luego el central
        'views/service_type_views.xml',
        'views/technician_views.xml',
        'views/equipment_views.xml',
        'views/maintenance_order_views.xml',
        'views/menu_views.xml',
    ],

    'installable': True,
    'application': True,
    'auto_install': False,

    'images': ['static/description/icon.png'],
}
