import {
  Action,
  Cancel,
  Content,
  Description,
  Overlay,
  Portal,
  Root,
  Title,
} from "@radix-ui/react-alert-dialog";

import {
  PRIMARY_BUTTON_CLASS,
  SECONDARY_BUTTON_CLASS,
} from "../../../shared/ui/tokens/button-classes";

type LeaveLessonDialogProps = {
  isOpen: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function LeaveLessonDialog(props: LeaveLessonDialogProps) {
  const { isOpen, onCancel, onConfirm } = props;

  return (
    <Root
      onOpenChange={(open) => {
        if (!open) {
          onCancel();
        }
      }}
      open={isOpen}
    >
      <Portal>
        <Overlay className="fixed inset-0 z-50 bg-stone-950/35 backdrop-blur-sm data-[state=closed]:animate-none" />
        <Content className="fixed top-1/2 left-1/2 z-50 w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-[1.4rem] border border-[var(--lesson-border)] bg-[var(--lesson-surface)] p-6 shadow-[0_24px_56px_rgba(22,28,37,0.16)] outline-none focus:outline-none data-[state=open]:animate-none">
          <p className="font-medium text-[var(--lesson-text-soft)] text-sm">Leave lesson</p>
          <Title className="mt-3 font-semibold text-2xl text-[var(--lesson-text)] tracking-[-0.03em]">
            Stop this sprint now?
          </Title>
          <Description className="mt-3 text-[var(--lesson-text-muted)] text-sm leading-6">
            Your progress in this lesson may be lost. You can keep learning or leave and return to
            the path.
          </Description>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <Cancel asChild>
              <button className={`flex-1 ${SECONDARY_BUTTON_CLASS}`} type="button">
                Keep learning
              </button>
            </Cancel>
            <Action asChild>
              <button
                className={`flex-1 ${PRIMARY_BUTTON_CLASS}`}
                onClick={onConfirm}
                type="button"
              >
                Leave
              </button>
            </Action>
          </div>
        </Content>
      </Portal>
    </Root>
  );
}
