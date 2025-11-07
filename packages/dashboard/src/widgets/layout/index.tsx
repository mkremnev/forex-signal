import { Suspense } from "react";

import { NavigationMenu } from "radix-ui";
import { Link } from "react-router-dom";
import styled from "styled-components";
import { Outlet } from "react-router-dom";

const Root = styled.div`
  display: flex;
  flex-direction: column;
`;

const Main = styled.main`
  display: flex;
  flex-direction: column;
  margin-top: 100px;
  padding: 0 1rem;
`;

export default function Layout() {
  return (
    <Root>
      <NavigationMenu.Root className="w-full flex justify-center fixed top-2 left-0 right-0">
        <NavigationMenu.List className="list-none flex border rounded-2xl py-4 min-w-[320px] gap-5 justify-center shadow-gray-400 shadow">
          <NavigationMenu.Item>
            <Link to="/dashboard">Дашбоард</Link>
          </NavigationMenu.Item>
          <NavigationMenu.Item>
            <Link to="/settings">Настройки</Link>
          </NavigationMenu.Item>
        </NavigationMenu.List>
      </NavigationMenu.Root>

      <Main>
        <Suspense fallback={<div>Loading...</div>}>
          <Outlet />
        </Suspense>
      </Main>
    </Root>
  );
}
