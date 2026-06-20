import { Modal } from "./Modal";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  tone?: "danger" | "default";
  onConfirm: () => void;
  onCancel: () => void;
  pending?: boolean;
};

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  tone = "default",
  onConfirm,
  onCancel,
  pending = false,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      footer={(
        <div className="desk-actions flex flex-wrap justify-end gap-2">
          <button className="desk-button" type="button" disabled={pending} onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            className={tone === "danger" ? "desk-button border-ink bg-[#ffdad6] text-[#93000a] hover:bg-[#ffb4a8] hover:text-[#93000a]" : "desk-button"}
            type="button"
            disabled={pending}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      )}
    >
      <p className="text-sm text-muted">{message}</p>
    </Modal>
  );
}
