/** Toggle affordance for masked password fields (login / register). */
export function PasswordEyeIcon(props: { open: boolean }) {
  const { open } = props;

  return open ? (
    <svg
      aria-hidden="true"
      fill="none"
      height="18"
      viewBox="0 0 24 24"
      width="18"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7Z"
        stroke="currentColor"
        strokeWidth="1.7"
      />
      <path
        d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z"
        stroke="currentColor"
        strokeWidth="1.7"
      />
    </svg>
  ) : (
    <svg
      aria-hidden="true"
      fill="none"
      height="18"
      viewBox="0 0 24 24"
      width="18"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M4 4l16 16" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <path
        d="M10.6 10.6A2.7 2.7 0 0 0 12 15.2c1.5 0 2.7-1.2 2.7-2.7 0-.5-.1-1-.4-1.4"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <path
        d="M3.2 12s3.3-6.6 8.8-6.6c2 0 3.6.7 4.9 1.7M20.8 12s-3.3 6.6-8.8 6.6c-2 0-3.6-.7-4.9-1.7"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
    </svg>
  );
}
