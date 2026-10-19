import { Fragment, type ReactNode } from "react";

/**
 * Renders a catalogue `{placeholder}` template whose values are React nodes,
 * so a translated sentence can keep an inline element (a titled name, a link)
 * where its language puts it. Unknown placeholders stay visible, as in
 * `fillTemplate`.
 */
export function TemplateText({ template, values }: {
  template: string;
  values: Record<string, ReactNode>;
}) {
  const parts = template.split(/\{(\w+)\}/);
  return (
    <>
      {parts.map((part, index) =>
        index % 2 === 0
          ? part
          : <Fragment key={index}>{part in values ? values[part] : `{${part}}`}</Fragment>,
      )}
    </>
  );
}
