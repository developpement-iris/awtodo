import type { ClassNames } from "react-day-picker";

// Classes partagées entre DatePickerField et DateTimeField — pas d'import du
// CSS par défaut de react-day-picker : on pointe vers nos propres classes
// (voir DatePickerField.css, écrites aux jetons du projet).
export const DAY_PICKER_CLASS_NAMES: Partial<ClassNames> = {
  root: "date-picker-field__calendar",
  months: "date-picker-field__months",
  month: "date-picker-field__month",
  month_caption: "date-picker-field__caption",
  caption_label: "date-picker-field__caption-label",
  nav: "date-picker-field__nav",
  button_previous: "date-picker-field__nav-button",
  button_next: "date-picker-field__nav-button",
  month_grid: "date-picker-field__grid",
  weekdays: "date-picker-field__weekdays",
  weekday: "date-picker-field__weekday",
  week: "date-picker-field__week",
  day: "date-picker-field__day",
  day_button: "date-picker-field__day-button",
  selected: "date-picker-field__day-button--selected",
  today: "date-picker-field__day-button--today",
  outside: "date-picker-field__day-button--outside",
  disabled: "date-picker-field__day-button--disabled",
};
