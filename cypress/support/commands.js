// cypress/support/commands.js

Cypress.Commands.add('login', (username = 'admin', password = 'admin') => {
  cy.session([username, password], () => {
    cy.visit('/web/login')
    cy.get('#login').type(username)
    cy.get('#password').type(password)
    cy.get('button[type="submit"]').click()
    // Asegurar que el login fue exitoso esperando a que cargue el menú de inicio (la clase o_app_menu suele estar en odoo 16)
    cy.url().should('include', '/web')
  })
})

Cypress.Commands.add('openTechStoreApp', () => {
  cy.visit('/web')
  // Esperar a que cargue la interfaz base de Odoo
  cy.get('.o_main_navbar, .o_navbar', { timeout: 15000 }).should('exist')

  // Abrir el menú de aplicaciones (icono de los 9 puntos cuadrados)
  cy.get('.o_navbar_apps_menu button, .o_menu_toggle').first().click({ force: true })

  // Seleccionar la aplicación TechStore
  cy.get('[data-menu-xmlid="techstore_maintenance.menu_ts_root"]').should('be.visible').click({ force: true })

  // Asegurar que entramos esperando que el nombre de la app cambie en la barra superior
  cy.get('.o_menu_brand').should('contain', 'TechStore')
})
