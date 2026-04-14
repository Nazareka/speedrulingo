import { motion } from "framer-motion";
import type { ReactNode } from "react";

import { QUICK_TRANSITION } from "../../../shared/ui/tokens/motion";

type LessonItemMotionSectionProps = {
  itemKey: string;
  prefersReducedMotion: boolean | null;
  className: string;
  children: ReactNode;
  /** Vertical motion when reduced motion is off (main lesson uses exit -4 / initial 6; kana uses 8 / 12). */
  motionY: { exit: number; initial: number };
};

/**
 * Framer wrapper for the active lesson item card. When used under `AnimatePresence`, the **parent**
 * must set React `key={currentItem.item_id}` on this component — a `key` only on the inner
 * `motion.section` is not enough for exit/enter animations.
 */
export function LessonItemMotionSection(props: LessonItemMotionSectionProps) {
  const { itemKey, prefersReducedMotion, className, children, motionY } = props;

  return (
    <motion.section
      animate={{ opacity: 1, y: 0 }}
      className={className}
      exit={{ opacity: 0, y: prefersReducedMotion ? 0 : motionY.exit }}
      initial={{ opacity: 0, y: prefersReducedMotion ? 0 : motionY.initial }}
      key={itemKey}
      transition={prefersReducedMotion ? { duration: 0 } : QUICK_TRANSITION}
    >
      {children}
    </motion.section>
  );
}
