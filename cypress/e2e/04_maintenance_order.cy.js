describe('Órdenes de Mantenimiento E2E', () => {
  beforeEach(() => {
    cy.login()
  })

  it('Debe crear una orden de mantenimiento y avanzar a diagnóstico', () => {
    cy.openTechStoreApp()

    // Navegar a Mantenimientos > Órdenes
    cy.get('button[data-menu-xmlid="techstore_maintenance.menu_ts_maintenance"]').click({ force: true })
    cy.get('a[data-menu-xmlid="techstore_maintenance.menu_ts_maintenance_orders"]').click({ force: true })

    // Odoo puede cargar en vista kanban o list.
    // Usamos selectores combinados que Cypress esperará y reintentará automáticamente.
    cy.get('.o_list_button_add, .o-kanban-button-new, .o_kanban_button_new').first().click({ force: true })

    // Llenar campos relacionales (Cliente, Equipo, Tipo de Servicio)
    cy.get('div[name="client_id"] input').click()
    cy.get('ul.ui-autocomplete:visible li a').first().click()

    cy.get('div[name="equipment_id"] input').click()
    cy.get('ul.ui-autocomplete:visible li a').first().click()

    cy.get('div[name="service_type_id"] input').click()
    cy.get('ul.ui-autocomplete:visible li a').first().click()

    // Asignar Técnico explícitamente buscando el creado en el test anterior
    cy.get('div[name="technician_id"] input').click().clear().type('Cypress')
    cy.get('ul.ui-autocomplete:visible li a').contains('Cypress').click()

    // Llenar problema y estado físico
    cy.get('div[name="problem_description"] textarea').type('Pantalla rota reportada por cliente E2E.')
    cy.get('div[name="physical_condition"] textarea').type('Carcasa con rayones E2E.')

    // Guardar
    cy.get('.o_form_button_save').click({ force: true })

    // Validar estado inicial 'received' (indicado en la barra de progreso)
    cy.get('div[name="state"] button.o_arrow_button_current').should('contain', 'Recibido') // u otro label dependiendo de la traducción, asumimos el default de odoo

    // Iniciar Diagnóstico
    cy.get('button[name="action_start_diagnosis"]').click({ force: true })

    // Validar transición a diagnóstico
    cy.get('div[name="state"] button.o_arrow_button_current').should('contain', 'Diagnóstico')
  })
})
