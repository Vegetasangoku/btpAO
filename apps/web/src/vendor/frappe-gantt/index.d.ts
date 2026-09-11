// Minimal hand-written type surface for the vendored frappe-gantt ESM bundle (v1.2.2,
// MIT, https://github.com/frappe/gantt). Only the members actually used by
// interactive-gantt-chart.tsx are declared -- this is not a full upstream typing.
declare module "@/vendor/frappe-gantt/frappe-gantt.es.js" {
  export interface FrappeGanttTask {
    id: string;
    name: string;
    start: string;
    end: string;
    progress?: number;
    dependencies?: string;
    custom_class?: string;
  }

  export interface FrappeGanttOptions {
    view_mode?: "Day" | "Week" | "Month" | "Year";
    language?: string;
    readonly?: boolean;
    readonly_dates?: boolean;
    readonly_progress?: boolean;
    move_dependencies?: boolean;
    popup_on?: "click" | "hover";
    popup?: false | ((ctx: any) => void | false | string);
    on_click?: (task: FrappeGanttTask) => void;
    on_date_change?: (task: FrappeGanttTask, start: Date, end: Date) => void;
    on_progress_change?: (task: FrappeGanttTask, progress: number) => void;
    on_view_change?: (mode: any) => void;
    /* Options de géométrie réellement lues par le moteur (voir frappe-gantt.es.js :
       `bar_height: 30` et `padding: 18` dans les valeurs par défaut, utilisées pour
       calculer la hauteur des barres et l'espacement des lignes). Elles manquaient
       dans cette déclaration écrite à la main, ce qui les rendait inutilisables
       depuis TypeScript alors qu'elles fonctionnent à l'exécution. */
    bar_height?: number;
    padding?: number;
    bar_corner_radius?: number;
    arrow_curve?: number;
    column_width?: number;
  }

  export default class Gantt {
    constructor(
      wrapper: string | HTMLElement,
      tasks: FrappeGanttTask[],
      options?: FrappeGanttOptions
    );
    refresh(tasks: FrappeGanttTask[]): void;
    change_view_mode(mode: string): void;
  }
}
