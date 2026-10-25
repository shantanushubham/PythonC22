import { Link } from "react-router-dom";
import { EmptyState } from "../components/ui";

export default function NotFound() {
  return (
    <EmptyState icon="alert" title="Page not found" action={<Link className="btn btn-primary btn-md" to="/">Back to dashboard</Link>}>
      That page does not exist.
    </EmptyState>
  );
}
