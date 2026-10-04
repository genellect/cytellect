import type { ReactNode } from "react";
import styles from "./product.module.css";

// Adapted from COMPASS OfficialCoreSections.tsx, SectionHeading.
// Source commit 4805fb6df9e5a0bd267aef9cfa440174ccac5fb1.
// Copyright (c) 2026 Yuto Matsui. All rights reserved.
// Reuse and adaptation expressly authorized by the owner for Cytellect.
// Removed reveal effects and decorative labels; retained title/description semantics.
export function EditorialHeading({ title, description, id }: {title: ReactNode; description?: ReactNode; id: string}) {
  return <header className={styles.sectionHeading}>
    <h2 id={id}>{title}</h2>
    {description ? <div className={styles.description}>{description}</div> : null}
  </header>;
}
