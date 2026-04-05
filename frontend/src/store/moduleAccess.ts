import type { ModulosPermitidos } from "../types";
import { SYSTEM_MODULES } from "../config/systemModules";

export type ModuleSection = {
  key: string;
  label: string;
};

export type ModuleDefinition = {
  key: string;
  label: string;
  description?: string;
  sections?: ModuleSection[];
};

export type ModuleAccessEntry = {
  enabled: boolean;
  sections: Record<string, boolean>;
};

export type ModuleAccessState = Record<string, ModuleAccessEntry>;

export const MODULE_DEFINITIONS: ModuleDefinition[] = SYSTEM_MODULES.map(
  ({ key, label, description, sections }) => ({
    key,
    label,
    description,
    sections: sections.map((section) => ({
      key: section.key,
      label: section.label,
    })),
  })
);

const prettifyLabel = (value: string): string =>
  value
    .split(/[_-]/)
    .filter(Boolean)
    .map((chunk) => chunk.charAt(0).toUpperCase() + chunk.slice(1))
    .join(" ");

const inferSectionsFromIncoming = (incoming: unknown): ModuleSection[] => {
  const sectionKeys = new Set<string>();

  if (Array.isArray(incoming)) {
    incoming.forEach((item) => {
      if (typeof item === "string" && item.trim()) {
        sectionKeys.add(item);
      }
    });
  } else if (incoming && typeof incoming === "object") {
    const record = incoming as Record<string, unknown>;
    const recordSections = record.sections;

    if (Array.isArray(recordSections)) {
      recordSections.forEach((item) => {
        if (typeof item === "string" && item.trim()) {
          sectionKeys.add(item);
        }
      });
    } else if (recordSections && typeof recordSections === "object") {
      Object.keys(recordSections).forEach((key) => {
        if (key.trim()) {
          sectionKeys.add(key);
        }
      });
    }

    Object.keys(record).forEach((key) => {
      if (key !== "enabled" && key !== "sections" && key.trim()) {
        sectionKeys.add(key);
      }
    });
  }

  return Array.from(sectionKeys).map((sectionKey) => ({
    key: sectionKey,
    label: prettifyLabel(sectionKey),
  }));
};

export const getModuleDefinitions = (
  access?: ModulosPermitidos | null
): ModuleDefinition[] => {
  if (!access) {
    return MODULE_DEFINITIONS;
  }

  const knownByKey = new Map(
    MODULE_DEFINITIONS.map((moduleDef) => [moduleDef.key, moduleDef])
  );
  const dynamicDefinitions: ModuleDefinition[] = [];

  Object.entries(access).forEach(([moduleKey, incoming]) => {
    if (knownByKey.has(moduleKey)) {
      return;
    }
    dynamicDefinitions.push({
      key: moduleKey,
      label: prettifyLabel(moduleKey),
      description: "Módulo agregado dinámicamente.",
      sections: inferSectionsFromIncoming(incoming),
    });
  });

  return [...MODULE_DEFINITIONS, ...dynamicDefinitions];
};

export const createEmptyModuleAccess = (
  moduleDefinitions: ModuleDefinition[] = MODULE_DEFINITIONS
): ModuleAccessState => {
  return moduleDefinitions.reduce<ModuleAccessState>((acc, moduleDef) => {
    const sections = (moduleDef.sections ?? []).reduce<Record<string, boolean>>(
      (sectionAcc, section) => {
        sectionAcc[section.key] = false;
        return sectionAcc;
      },
      {}
    );
    acc[moduleDef.key] = {
      enabled: false,
      sections,
    };
    return acc;
  }, {});
};

export const createFullModuleAccess = (): ModuleAccessState => {
  return MODULE_DEFINITIONS.reduce<ModuleAccessState>((acc, moduleDef) => {
    const sections = (moduleDef.sections ?? []).reduce<Record<string, boolean>>(
      (sectionAcc, section) => {
        sectionAcc[section.key] = true;
        return sectionAcc;
      },
      {}
    );
    acc[moduleDef.key] = {
      enabled: true,
      sections,
    };
    return acc;
  }, {});
};

export const normalizeModuleAccess = (
  access?: ModulosPermitidos | null
): ModuleAccessState => {
  const moduleDefinitions = getModuleDefinitions(access);
  const normalized = createEmptyModuleAccess(moduleDefinitions);
  if (!access) {
    return normalized;
  }

  moduleDefinitions.forEach((moduleDef) => {
    const incoming = access[moduleDef.key];
    if (!incoming) {
      return;
    }
    const moduleState = normalized[moduleDef.key];
    const sections = moduleDef.sections ?? [];

    if (typeof incoming === "boolean") {
      moduleState.enabled = incoming;
      sections.forEach((section) => {
        moduleState.sections[section.key] = incoming;
      });
      return;
    }

    if (Array.isArray(incoming)) {
      sections.forEach((section) => {
        moduleState.sections[section.key] = incoming.includes(section.key);
      });
      moduleState.enabled = Object.values(moduleState.sections).some(Boolean);
      return;
    }

    if (typeof incoming === "object") {
      const incomingRecord = incoming as Record<string, unknown>;
      const enabledValue = incomingRecord.enabled;
      if (typeof enabledValue === "boolean") {
        moduleState.enabled = enabledValue;
      }

      const incomingSections = incomingRecord.sections;
      if (Array.isArray(incomingSections)) {
        sections.forEach((section) => {
          moduleState.sections[section.key] = incomingSections.includes(
            section.key
          );
        });
      } else if (incomingSections && typeof incomingSections === "object") {
        sections.forEach((section) => {
          moduleState.sections[section.key] = Boolean(
            (incomingSections as Record<string, boolean | undefined>)[section.key]
          );
        });
      } else {
        sections.forEach((section) => {
          if (section.key in incomingRecord) {
            moduleState.sections[section.key] = Boolean(incomingRecord[section.key]);
          }
        });
      }

      if (Object.values(moduleState.sections).some(Boolean)) {
        moduleState.enabled = true;
      }
    }
  });

  return normalized;
};

export const isModuleEnabled = (
  access: ModuleAccessState,
  moduleKey: string
): boolean => {
  const moduleEntry = access[moduleKey];
  if (!moduleEntry) {
    return false;
  }
  if (moduleEntry.enabled) {
    return true;
  }
  return Object.values(moduleEntry.sections ?? {}).some(Boolean);
};

export const isSectionEnabled = (
  access: ModuleAccessState,
  moduleKey: string,
  sectionKey: string
): boolean => {
  const moduleEntry = access[moduleKey];
  return Boolean(moduleEntry?.sections?.[sectionKey]);
};
