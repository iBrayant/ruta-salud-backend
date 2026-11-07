<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow">
  <meta name="color-scheme" content="light">
  <title>Ingresar · Ruta Salud Rural</title>
  <link rel="stylesheet" href="${url.resourcesPath}/css/ruta-salud.css">
</head>
<body>
  <main class="rs-pagina">
    <div class="rs-contenedor">
      <div class="rs-marca">
        <span class="rs-nombre">Ruta Salud Rural</span>
        <span class="rs-sub">Hospital San Rafael · Fusagasugá</span>
      </div>
      <div class="rs-tarjeta">
        <h1 class="rs-titulo"><#nested "header"></h1>
        <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
          <div class="rs-alerta rs-alerta-${message.type}" role="<#if message.type == 'error'>alert<#else>status</#if>">${kcSanitize(message.summary)?no_esc}</div>
        </#if>
        <#nested "form">
        <#if displayInfo>
          <div class="rs-info"><#nested "info"></div>
        </#if>
      </div>
      <p class="rs-pie">
        Acceso con OAuth 2.0. No se almacenan datos de pacientes. Tratamiento de datos según la Ley 1581 de 2012.<br>
        Prototipo académico — Maratón de Programación UCundinamarca 2026.
      </p>
    </div>
  </main>
</body>
</html>
</#macro>
