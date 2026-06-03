// cypress/support/e2e.js
import './commands'

// Ocultar errores de origen cruzado de Odoo (a veces ocurren con scripts de terceros)
Cypress.on('uncaught:exception', (err, runnable) => {
  return false
})
