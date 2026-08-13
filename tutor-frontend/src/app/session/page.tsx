import { redirect } from "next/navigation";

/** Legacy Ministros-style session URL. The product lesson lives under /subjects. */
export default function SessionPage() {
  redirect("/");
}
