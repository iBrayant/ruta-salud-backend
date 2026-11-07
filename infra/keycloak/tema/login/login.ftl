<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username','password'); section>
  <#if section = "header">
    Ingresar
  <#elseif section = "form">
    <p class="rs-texto">Use su cuenta institucional.</p>
    <form id="kc-form-login" class="rs-form" action="${url.loginAction}" method="post" novalidate>
      <div class="rs-campo">
        <label for="username">Usuario</label>
        <input id="username" name="username" type="text" value="${(login.username!'')}" autocomplete="username" autofocus
               <#if messagesPerField.existsError('username','password')>aria-invalid="true" aria-describedby="rs-error-login"</#if>>
      </div>
      <div class="rs-campo">
        <label for="password">Contraseña</label>
        <input id="password" name="password" type="password" autocomplete="current-password"
               <#if messagesPerField.existsError('username','password')>aria-invalid="true" aria-describedby="rs-error-login"</#if>>
      </div>
      <#if messagesPerField.existsError('username','password')>
        <div id="rs-error-login" class="rs-alerta rs-alerta-error" role="alert">${kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc}</div>
      </#if>
      <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>>
      <button class="rs-boton" name="login" id="kc-login" type="submit">Ingresar</button>
    </form>
    <p class="rs-nota">Después de 5 intentos fallidos la cuenta se bloquea temporalmente.</p>
  </#if>
</@layout.registrationLayout>
