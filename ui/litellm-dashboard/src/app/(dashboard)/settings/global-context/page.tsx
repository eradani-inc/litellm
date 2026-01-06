"use client";

import GlobalContextSettings from "@/components/global_context_settings";
import useAuthorized from "@/app/(dashboard)/hooks/useAuthorized";

const GlobalContextPage = () => {
  const { accessToken } = useAuthorized();

  return <GlobalContextSettings accessToken={accessToken} />;
};

export default GlobalContextPage;
