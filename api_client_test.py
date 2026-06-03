#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api_client_test.py
==================
Cliente de pruebas externo para la API REST del modulo techstore_maintenance.
Ejecuta una suite completa de pruebas funcionales, de seguridad y de rendimiento
contra el servidor Odoo activo, sin necesidad del framework interno de Odoo.

Uso:
    python api_client_test.py

Requisitos:
    pip install requests

Configuracion:
    Ajustar BASE_URL, DB_NAME, USERNAME y PASSWORD segun el entorno de ejecucion.
    El servidor Odoo debe estar activo y el modulo techstore_maintenance instalado.
"""
import json
import statistics
import sys
import time
from datetime import datetime, date


try:
    import requests
except ImportError:
    print("ERROR: El modulo 'requests' no esta instalado.")
    print("Ejecute: pip install requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Configuracion del entorno
# ---------------------------------------------------------------------------
BASE_URL = "http://localhost:8069"
DB_NAME = "techstore_db"
USERNAME = "admin"
PASSWORD = "admin"
REQUEST_TIMEOUT = 30  # segundos


# ---------------------------------------------------------------------------
# Clase principal
# ---------------------------------------------------------------------------
class TechStoreApiTestClient:
    """
    Suite de pruebas de API para el modulo techstore_maintenance.
    Implementa los casos de prueba PF (funcional), PS (seguridad) y PR (rendimiento).
    """

    def __init__(self):
        self.session = requests.Session()
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results = []
        self.context = {}
        self.created = {
            "clients": [],
            "service-types": [],
            "technicians": [],
            "equipment": [],
            "maintenance-orders": [],
        }

    # -----------------------------------------------------------------------
    # Autenticacion
    # -----------------------------------------------------------------------
    def authenticate(self):
        """Autentica contra Odoo mediante el endpoint de sesion JSON-RPC."""
        print(f"  Autenticando como '{USERNAME}' en '{DB_NAME}'...")
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "db": DB_NAME,
                "login": USERNAME,
                "password": PASSWORD,
            },
            "id": 1,
        }
        response = self.session.post(
            f"{BASE_URL}/web/session/authenticate",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json().get("result", {})
        if not result.get("uid"):
            raise RuntimeError(
                "Autenticacion fallida. Verifique credenciales y nombre de base de datos."
            )
        print(f"  Autenticado correctamente. UID: {result['uid']}")

    # -----------------------------------------------------------------------
    # Metodo central de peticion HTTP
    # -----------------------------------------------------------------------
    def request(self, method, path, body=None, raw_body=None, use_session=True):
        """
        Realiza una peticion HTTP al servidor Odoo.
        Retorna un diccionario con status, elapsed, headers, json y text.
        """
        client = self.session if use_session else requests
        headers = {"Content-Type": "application/json"}
        start = time.perf_counter()
        response = client.request(
            method=method,
            url=BASE_URL + path,
            json=body if raw_body is None else None,
            data=raw_body,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
        )
        elapsed = time.perf_counter() - start
        parsed = None
        if "application/json" in response.headers.get("Content-Type", ""):
            try:
                parsed = response.json()
            except ValueError:
                pass
        return {
            "status": response.status_code,
            "elapsed": elapsed,
            "headers": dict(response.headers),
            "json": parsed,
            "text": response.text,
        }

    # -----------------------------------------------------------------------
    # Registro de resultados
    # -----------------------------------------------------------------------
    def record(self, case_id, description, request_desc, expected, actual,
               passed, elapsed, category):
        """Registra el resultado de un caso de prueba."""
        self.results.append({
            "case_id": case_id,
            "description": description,
            "request": request_desc,
            "expected": expected,
            "actual": actual,
            "passed": passed,
            "elapsed": elapsed,
            "category": category,
        })
        status_str = "PASS" if passed else "FAIL"
        elapsed_str = f"{elapsed:.3f}s" if elapsed is not None else "N/A"
        print(f"    [{status_str}] {case_id} — {description} ({elapsed_str})")

    def fmt(self, resp):
        """Formatea la respuesta para el campo 'actual' del resultado."""
        body = resp["json"] if resp["json"] is not None else resp["text"][:300]
        return f"HTTP {resp['status']} | {json.dumps(body, ensure_ascii=False, default=str)[:400]}"

    # -----------------------------------------------------------------------
    # Preparacion de datos maestros
    # -----------------------------------------------------------------------
    def prepare_master_data(self):
        """Crea los datos maestros necesarios para la ejecucion de las pruebas."""
        print("\n  Preparando datos maestros...")
        suffix = self.run_id

        # Cliente
        resp = self.request("POST", "/api/techstore/clients", body={
            "name": f"Cliente Prueba API {suffix}",
            "email": f"cliente.{suffix}@test.com",
            "phone": "0990000001",
            "is_company": True,
            "active": True,
        })
        self._assert_ok(resp, "Crear cliente maestro")
        client_id = resp["json"]["id"]
        self.created["clients"].append(client_id)
        self.context["client_id"] = client_id

        # Tipo de servicio
        resp = self.request("POST", "/api/techstore/service-types", body={
            "name": f"Servicio API {suffix}",
            "description": "Creado por cliente de prueba automatizado",
            "active": True,
        })
        self._assert_ok(resp, "Crear tipo de servicio maestro")
        svc_id = resp["json"]["id"]
        self.created["service-types"].append(svc_id)
        self.context["service_type_id"] = svc_id

        # Tecnico
        emp_number = f"EMP-{suffix[-6:]}"
        resp = self.request("POST", "/api/techstore/technicians", body={
            "name": f"Tecnico API {suffix}",
            "employee_number": emp_number,
            "email": f"tecnico.{suffix}@test.com",
            "specialty_hardware": True,
            "specialty_software": True,
            "state": "active",
            "availability": "available",
        })
        self._assert_ok(resp, "Crear tecnico maestro")
        tech_id = resp["json"]["id"]
        self.created["technicians"].append(tech_id)
        self.context["technician_id"] = tech_id

        # Equipo
        serial = f"SN-EXT-{suffix}"
        resp = self.request("POST", "/api/techstore/equipment", body={
            "name": f"Laptop API {suffix}",
            "equipment_type": "laptop",
            "brand": "Lenovo",
            "model_name": "ThinkPad API",
            "serial_number": serial,
            "current_state": "faulty",
            "active": True,
            "client_id": client_id,
        })
        self._assert_ok(resp, "Crear equipo maestro")
        eq_id = resp["json"]["id"]
        self.created["equipment"].append(eq_id)
        self.context["equipment_id"] = eq_id

        print(f"  Datos maestros creados: cliente={client_id}, "
              f"tecnico={tech_id}, equipo={eq_id}")

    def _assert_ok(self, resp, action):
        if resp["status"] >= 400:
            detail = resp["json"] or resp["text"]
            raise RuntimeError(f"Fallo al {action}: HTTP {resp['status']} — {detail}")

    # -----------------------------------------------------------------------
    # Pruebas funcionales
    # -----------------------------------------------------------------------
    def run_functional_tests(self):
        print("\n  [FUNCIONAL]")

        # PF-01: Dashboard
        resp = self.request("GET", "/api/techstore/dashboard")
        passed = (resp["status"] == 200
                  and isinstance(resp["json"], dict)
                  and "total_orders" in resp["json"])
        self.record("PF-01", "Consultar dashboard de metricas",
                    "GET /api/techstore/dashboard",
                    "HTTP 200 con campo total_orders",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-02: Listado de ordenes con paginacion
        resp = self.request("GET", "/api/techstore/maintenance-orders?limit=10&offset=0")
        passed = (resp["status"] == 200
                  and "count" in (resp["json"] or {})
                  and "items" in (resp["json"] or {}))
        self.record("PF-02", "Listar ordenes de mantenimiento paginadas",
                    "GET /api/techstore/maintenance-orders?limit=10",
                    "HTTP 200 con campos count e items",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-03: Crear orden
        order_payload = {
            "client_id": self.context["client_id"],
            "equipment_id": self.context["equipment_id"],
            "service_type_id": self.context["service_type_id"],
            "priority": "2",
            "reception_date": str(date.today()),
            "problem_description": "Equipo no enciende tras actualizacion de firmware.",
            "physical_condition": "Sin golpes ni danos fisicos externos.",
        }
        resp = self.request("POST", "/api/techstore/maintenance-orders", body=order_payload)
        passed = (resp["status"] == 201
                  and (resp["json"] or {}).get("state") == "received")
        order_id = (resp["json"] or {}).get("id")
        if order_id:
            self.created["maintenance-orders"].append(order_id)
            self.context["order_id"] = order_id
        self.record("PF-03", "Crear orden de mantenimiento",
                    "POST /api/techstore/maintenance-orders",
                    "HTTP 201 y state=received",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        order_id = self.context.get("order_id")
        if not order_id:
            print("  ADVERTENCIA: No se pudo crear la orden. Los casos PF-04 a PF-13 seran omitidos.")
            return

        # PF-04: Asignar tecnico
        resp = self.request(
            "POST",
            f"/api/techstore/maintenance-orders/{order_id}/actions/assign-technician",
            body={"technician_id": self.context["technician_id"]},
        )
        assigned_id = ((resp["json"] or {}).get("technician_id") or {}).get("id")
        passed = (resp["status"] == 200 and assigned_id == self.context["technician_id"])
        self.record("PF-04", "Asignar tecnico a la orden",
                    "POST .../actions/assign-technician",
                    "HTTP 200 y technician_id igual al enviado",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-05: Avanzar a diagnostico
        resp = self.request(
            "POST",
            f"/api/techstore/maintenance-orders/{order_id}/actions/start-diagnosis",
            body={},
        )
        passed = (resp["status"] == 200 and (resp["json"] or {}).get("state") == "diagnosis")
        self.record("PF-05", "Iniciar diagnostico de la orden",
                    "POST .../actions/start-diagnosis",
                    "HTTP 200 y state=diagnosis",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-06: Bloqueo de reparacion sin diagnostico escrito
        resp = self.request(
            "POST",
            f"/api/techstore/maintenance-orders/{order_id}/actions/start-repair",
            body={},
        )
        passed = resp["status"] == 400
        self.record("PF-06", "Bloquear avance a reparacion sin texto de diagnostico",
                    "POST .../actions/start-repair (sin diagnosis)",
                    "HTTP 400",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-07: Escribir diagnostico
        resp = self.request(
            "PATCH",
            f"/api/techstore/maintenance-orders/{order_id}",
            body={"diagnosis": "La bateria del equipo requiere reemplazo inmediato."},
        )
        passed = (resp["status"] == 200
                  and (resp["json"] or {}).get("diagnosis") == "La bateria del equipo requiere reemplazo inmediato.")
        self.record("PF-07", "Actualizar campo de diagnostico",
                    "PATCH /api/techstore/maintenance-orders/{id}",
                    "HTTP 200 y campo diagnosis persistido",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-08: Avanzar a reparacion
        resp = self.request(
            "POST",
            f"/api/techstore/maintenance-orders/{order_id}/actions/start-repair",
            body={},
        )
        passed = (resp["status"] == 200 and (resp["json"] or {}).get("state") == "repair")
        self.record("PF-08", "Iniciar reparacion de la orden",
                    "POST .../actions/start-repair",
                    "HTTP 200 y state=repair",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-09: Bloqueo de listo sin resolucion
        resp = self.request(
            "POST",
            f"/api/techstore/maintenance-orders/{order_id}/actions/mark-ready",
            body={},
        )
        passed = resp["status"] == 400
        self.record("PF-09", "Bloquear 'listo' sin texto de resolucion",
                    "POST .../actions/mark-ready (sin resolution)",
                    "HTTP 400",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-10: Escribir resolucion
        resp = self.request(
            "PATCH",
            f"/api/techstore/maintenance-orders/{order_id}",
            body={
                "resolution": "Se reemplazo la bateria por una unidad nueva de 65 W.",
                "parts_used": "Bateria compatible 65 W",
            },
        )
        passed = (resp["status"] == 200
                  and (resp["json"] or {}).get("resolution") == "Se reemplazo la bateria por una unidad nueva de 65 W.")
        self.record("PF-10", "Actualizar campo de resolucion y repuestos",
                    "PATCH /api/techstore/maintenance-orders/{id}",
                    "HTTP 200 y campo resolution persistido",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-11: Marcar listo
        resp = self.request(
            "POST",
            f"/api/techstore/maintenance-orders/{order_id}/actions/mark-ready",
            body={},
        )
        passed = (resp["status"] == 200 and (resp["json"] or {}).get("state") == "ready")
        self.record("PF-11", "Marcar orden lista para entrega",
                    "POST .../actions/mark-ready",
                    "HTTP 200 y state=ready",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-12: Marcar entregado
        resp = self.request(
            "POST",
            f"/api/techstore/maintenance-orders/{order_id}/actions/mark-delivered",
            body={},
        )
        passed = (resp["status"] == 200 and (resp["json"] or {}).get("state") == "delivered")
        self.record("PF-12", "Marcar orden como entregada",
                    "POST .../actions/mark-delivered",
                    "HTTP 200 y state=delivered",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-13: Cerrar orden
        resp = self.request(
            "POST",
            f"/api/techstore/maintenance-orders/{order_id}/actions/close",
            body={},
        )
        passed = (resp["status"] == 200 and (resp["json"] or {}).get("state") == "closed")
        self.record("PF-13", "Cerrar la orden finalizada",
                    "POST .../actions/close",
                    "HTTP 200 y state=closed",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-14: Consultar bitacora de auditoria
        resp = self.request(
            "GET",
            f"/api/techstore/maintenance-orders/{order_id}/audit-logs",
        )
        items = (resp["json"] or {}).get("items", [])
        passed = resp["status"] == 200 and len(items) >= 5
        self.record("PF-14", "Consultar bitacora de auditoria de la orden",
                    "GET .../audit-logs",
                    "HTTP 200 con minimo 5 entradas de auditoria",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

        # PF-15: Intentar modificar orden cerrada
        resp = self.request(
            "POST",
            f"/api/techstore/maintenance-orders/{order_id}/actions/start-diagnosis",
            body={},
        )
        passed = resp["status"] == 400
        self.record("PF-15", "Bloquear accion sobre orden cerrada",
                    "POST .../actions/start-diagnosis (orden cerrada)",
                    "HTTP 400",
                    self.fmt(resp), passed, resp["elapsed"], "Funcional")

    # -----------------------------------------------------------------------
    # Pruebas de seguridad
    # -----------------------------------------------------------------------
    def run_security_tests(self):
        print("\n  [SEGURIDAD]")

        # PS-01: Acceso anonimo rechazado
        resp = self.request("GET", "/api/techstore/dashboard", use_session=False)
        passed = (resp["status"] in (303, 401)
                  or (resp["status"] == 200
                      and "application/json" not in resp["headers"].get("Content-Type", "")))
        self.record("PS-01", "Verificar que el acceso anonimo sea rechazado",
                    "GET /api/techstore/dashboard sin sesion",
                    "Redireccion (303) o rechazo (401) sin datos JSON",
                    self.fmt(resp), passed, resp["elapsed"], "Seguridad")

        # PS-02: Recurso no registrado devuelve 404
        resp = self.request("GET", "/api/techstore/recurso-inexistente")
        passed = resp["status"] == 404
        self.record("PS-02", "Recurso no registrado retorna HTTP 404",
                    "GET /api/techstore/recurso-inexistente",
                    "HTTP 404",
                    self.fmt(resp), passed, resp["elapsed"], "Seguridad")

        # PS-03: Creacion directa de audit-log bloqueada
        order_id = self.context.get("order_id")
        resp = self.request("POST", "/api/techstore/audit-logs", body={
            "order_id": order_id,
            "event_type": "Manipulacion manual",
            "description": "Intento de escritura directa no autorizado",
        })
        passed = resp["status"] in (400, 403)
        self.record("PS-03", "Bloquear creacion directa del log de auditoria",
                    "POST /api/techstore/audit-logs",
                    "HTTP 400 o 403",
                    self.fmt(resp), passed, resp["elapsed"], "Seguridad")

        # PS-04: JSON invalido rechazado
        resp = self.request("POST", "/api/techstore/clients",
                            raw_body=b"{json-invalido: sin-comillas")
        passed = resp["status"] == 400
        self.record("PS-04", "JSON malformado retorna HTTP 400",
                    "POST /api/techstore/clients con cuerpo malformado",
                    "HTTP 400",
                    self.fmt(resp), passed, resp["elapsed"], "Seguridad")

        # PS-05: Accion no definida devuelve 404
        if order_id:
            resp = self.request(
                "POST",
                f"/api/techstore/maintenance-orders/{order_id}/actions/accion-falsa",
                body={},
            )
            passed = resp["status"] == 404
            self.record("PS-05", "Accion no definida retorna HTTP 404",
                        "POST .../actions/accion-falsa",
                        "HTTP 404",
                        self.fmt(resp), passed, resp["elapsed"], "Seguridad")

        # PS-06: Cabecera Content-Type en respuestas
        resp = self.request("GET", "/api/techstore/dashboard")
        ct = resp["headers"].get("Content-Type", "")
        passed = "application/json" in ct
        self.record("PS-06", "Respuestas incluyen Content-Type application/json",
                    "GET /api/techstore/dashboard (verificacion de cabeceras)",
                    "Content-Type: application/json",
                    f"Content-Type: {ct}", passed, resp["elapsed"], "Seguridad")

    # -----------------------------------------------------------------------
    # Pruebas de rendimiento
    # -----------------------------------------------------------------------
    def run_performance_tests(self):
        print("\n  [RENDIMIENTO]")
        n = 10

        dashboard_times = []
        for _ in range(n):
            resp = self.request("GET", "/api/techstore/dashboard")
            dashboard_times.append(resp["elapsed"])

        order_times = []
        for _ in range(n):
            resp = self.request("GET", "/api/techstore/maintenance-orders?limit=20")
            order_times.append(resp["elapsed"])

        avg_d = statistics.mean(dashboard_times)
        self.record("PR-01", f"Latencia del dashboard ({n} llamadas repetidas)",
                    f"10x GET /api/techstore/dashboard",
                    "Tiempo promedio documentado; estabilidad entre llamadas",
                    f"avg={avg_d:.4f}s, min={min(dashboard_times):.4f}s, max={max(dashboard_times):.4f}s",
                    True, avg_d, "Rendimiento")

        avg_o = statistics.mean(order_times)
        self.record("PR-02", f"Latencia del listado de ordenes ({n} llamadas repetidas)",
                    f"10x GET /api/techstore/maintenance-orders?limit=20",
                    "Tiempo promedio documentado; estabilidad entre llamadas",
                    f"avg={avg_o:.4f}s, min={min(order_times):.4f}s, max={max(order_times):.4f}s",
                    True, avg_o, "Rendimiento")

        print(f"    Dashboard:  avg={avg_d:.4f}s  min={min(dashboard_times):.4f}s  max={max(dashboard_times):.4f}s")
        print(f"    Ordenes:    avg={avg_o:.4f}s  min={min(order_times):.4f}s  max={max(order_times):.4f}s")

    # -----------------------------------------------------------------------
    # Limpieza de datos
    # -----------------------------------------------------------------------
    def cleanup(self):
        """Elimina los registros creados durante la ejecucion."""
        print("\n  Limpiando datos de prueba...")
        order = ["maintenance-orders", "equipment", "technicians",
                 "service-types", "clients"]
        for resource in order:
            for rec_id in self.created[resource]:
                try:
                    self.request("DELETE", f"/api/techstore/{resource}/{rec_id}")
                except Exception:
                    pass

    # -----------------------------------------------------------------------
    # Reporte
    # -----------------------------------------------------------------------
    def print_summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        all_times = [r["elapsed"] for r in self.results if r["elapsed"] is not None]
        avg_time = statistics.mean(all_times) if all_times else 0

        print("\n" + "=" * 60)
        print("RESUMEN DE EJECUCION")
        print("=" * 60)
        print(f"  Total de casos  : {total}")
        print(f"  Aprobados (PASS): {passed}")
        print(f"  Fallidos  (FAIL): {failed}")
        print(f"  Tasa de exito   : {(passed / total * 100):.1f}%")
        print(f"  Tiempo promedio : {avg_time:.4f} s")
        print(f"  Fecha           : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if failed > 0:
            print("\n  CASOS FALLIDOS:")
            for r in self.results:
                if not r["passed"]:
                    print(f"    - {r['case_id']}: {r['description']}")
                    print(f"      Esperado: {r['expected']}")
                    print(f"      Obtenido: {r['actual']}")
        print("=" * 60)
        return failed == 0

    def save_report(self, path="api_test_results.json"):
        """Guarda los resultados en formato JSON para integracion con CI."""
        report = {
            "run_id": self.run_id,
            "base_url": BASE_URL,
            "db": DB_NAME,
            "executed_at": datetime.now().isoformat(),
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r["passed"]),
                "failed": sum(1 for r in self.results if not r["passed"]),
            },
            "results": self.results,
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
        print(f"\n  Reporte guardado en: {path}")

    # -----------------------------------------------------------------------
    # Punto de entrada
    # -----------------------------------------------------------------------
    def run(self):
        print("=" * 60)
        print("SUITE DE PRUEBAS EXTERNAS — API TechStore Maintenance")
        print(f"Servidor : {BASE_URL}")
        print(f"Base de datos: {DB_NAME}")
        print(f"Inicio   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        try:
            self.authenticate()
            self.prepare_master_data()
            self.run_functional_tests()
            self.run_security_tests()
            self.run_performance_tests()
        except RuntimeError as exc:
            print(f"\n  ERROR CRITICO: {exc}")
            print("  La suite se interrumpio antes de completarse.")
        finally:
            self.cleanup()

        success = self.print_summary()
        self.save_report()
        return 0 if success else 1


if __name__ == "__main__":
    client = TechStoreApiTestClient()
    sys.exit(client.run())
