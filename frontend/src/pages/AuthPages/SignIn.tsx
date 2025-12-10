import PageMeta from "../../components/common/PageMeta";
import AuthLayout from "./AuthPageLayout";
import SignInForm from "../../components/auth/SignInForm";

export default function SignIn() {
  return (
    <>
      <PageMeta
        title="Sign In | BidKing"
        description="Sign in to your BidKing account to discover federal contract opportunities"
      />
      <AuthLayout>
        <SignInForm />
      </AuthLayout>
    </>
  );
}
