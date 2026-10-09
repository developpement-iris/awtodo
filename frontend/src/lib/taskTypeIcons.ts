import {
  BookOpen,
  Bug,
  CirclePlus,
  Code,
  FileText,
  FlaskConical,
  Lightbulb,
  Rocket,
  Search,
  Shield,
  Tag,
  TrendingUp,
  Users,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import type { TaskTypeIcon } from "../types/watodo";

// Miroir de `apps.tasks.models.TaskType.ICON_CHOICES` — liste courte, sans
// couleur (une couleur = un axe, voir docs/charte-graphique.md).
export const TASK_TYPE_ICONS: Record<TaskTypeIcon, LucideIcon> = {
  wrench: Wrench,
  circle_plus: CirclePlus,
  trending_up: TrendingUp,
  flask: FlaskConical,
  rocket: Rocket,
  code: Code,
  lightbulb: Lightbulb,
  book: BookOpen,
  search: Search,
  bug: Bug,
  file: FileText,
  users: Users,
  shield: Shield,
  tag: Tag,
};

export const TASK_TYPE_ICON_KEYS = Object.keys(TASK_TYPE_ICONS) as TaskTypeIcon[];
