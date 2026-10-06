"use strict";

const { Menu, app } = require("electron");

function buildMenu({ productName, onQuit }) {
  const quit = {
    label: process.platform === "darwin" ? `Quit ${productName}` : "Quit",
    accelerator: process.platform === "darwin" ? "Command+Q" : "Alt+F4",
    click: () => onQuit(),
  };
  const edit = {
    label: "Edit",
    submenu: [
      { role: "undo" },
      { role: "redo" },
      { type: "separator" },
      { role: "cut" },
      { role: "copy" },
      { role: "paste" },
      { role: "selectAll" },
    ],
  };
  const view = {
    label: "View",
    submenu: [{ role: "reload" }, { role: "togglefullscreen" }],
  };
  const windowMenu = {
    label: "Window",
    submenu: [{ role: "minimize" }, { role: "close" }],
  };
  const template = [];
  if (process.platform === "darwin") {
    template.push({
      label: productName,
      submenu: [{ role: "about" }, { type: "separator" }, quit],
    });
  } else {
    template.push({ label: "File", submenu: [quit] });
  }
  template.push(edit, view, windowMenu);
  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
  return menu;
}

function quitApp() {
  app.quit();
}

module.exports = { buildMenu, quitApp };
