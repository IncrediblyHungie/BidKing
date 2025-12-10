import PageMeta from "../../components/common/PageMeta";
import AuthLayout from "./AuthPageLayout";
import SignUpForm from "../../components/auth/SignUpForm";

export default function SignUp() {
  return (
    <>
      <PageMeta
        title="Sign Up | BidKing"
        description="Create your BidKing account to start discovering federal contract opportunities"
      />
      <AuthLayout>
        <SignUpForm />
      </AuthLayout>
    </>
  );
}
