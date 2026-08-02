import { redirect } from "next/navigation";

/** The dashboard is now the home screen; keep old links working. */
export default function DashboardRedirect() {
  redirect("/");
}
