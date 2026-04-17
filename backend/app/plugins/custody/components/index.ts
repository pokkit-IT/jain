import { ChildrenScreen } from "./ChildrenScreen";
import { CustodyHome } from "./CustodyHome";
import { EventForm } from "./EventForm";
import { ExpenseForm } from "./ExpenseForm";
import { ExportSheet } from "./ExportSheet";
import { ScheduleForm } from "./ScheduleForm";
import { ScheduleListScreen } from "./ScheduleListScreen";
import { TextCaptureForm } from "./TextCaptureForm";

declare const globalThis: {
  JainPlugins?: Record<string, Record<string, unknown>>;
};

globalThis.JainPlugins = globalThis.JainPlugins || {};
globalThis.JainPlugins.custody = {
  CustodyHome,
  ExpenseForm,
  TextCaptureForm,
  EventForm,
  ScheduleForm,
  ScheduleListScreen,
  ChildrenScreen,
  ExportSheet,
};

export {
  ChildrenScreen, CustodyHome, EventForm, ExpenseForm, ExportSheet,
  ScheduleForm, ScheduleListScreen, TextCaptureForm,
};
