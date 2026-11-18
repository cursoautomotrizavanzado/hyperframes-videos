// AutoDiag Video Studio — versión DroidScript (alternativa al APK compilado)
// 1) Crea en DroidScript una app nueva tipo "HTML" o "JavaScript" llamada AutoDiag.
// 2) Copia en su carpeta: index.html, cloud_bundle.js, manifest.json, icon.svg, icon-192.png, icon-512.png
// 3) Guarda este archivo como el script principal (AutoDiag.js) y ejecútala.
// 4) Para generar el APK: menú de DroidScript → "Build APK" (plugin APKBuilder).

var web;

function OnStart() {
  app.SetOrientation("Portrait");
  app.SetScreenMode("Full");
  app.EnableBackKey(false);
  if (app.CheckPermission && app.CheckPermission("Storage")) app.GetPermission("Storage", function () {});

  var lay = app.CreateLayout("Linear", "VCenter,FillXY");
  lay.SetBackColor("#080D16");

  // WebView con acceso a archivos locales y a internet (Gemini y GitHub permiten CORS)
  web = app.CreateWebView(1, 1, "IgnoreErrors,NoScrollBars,AllowRemote,AllowZoom,UseBrowser");
  web.SetBackColor("#080D16");
  web.SetOnProgress(function (p) { if (p >= 100) app.HideProgress(); });
  // Puente: la página usa window.app (app.CreateFile / app.OpenUrl) para guardar MP4 y abrir enlaces
  web.SetInject && web.SetInject("app.js");
  lay.AddChild(web);
  app.AddLayout(lay);

  app.ShowProgress("Cargando AutoDiag…");
  web.LoadUrl("file://" + app.GetAppPath() + "/index.html");
}

function OnBack() {
  var yes = app.CreateYesNoDialog("¿Salir de AutoDiag Video Studio?");
  yes.SetOnTouch(function (r) { if (r === "Yes") app.Exit(); });
  yes.Show();
}
