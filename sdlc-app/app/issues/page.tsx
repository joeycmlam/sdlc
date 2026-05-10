import { redirect } from "next/navigation";

export default function IssuesIndex() {
  redirect("/issues/new");
}
