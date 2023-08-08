import { Route, Routes } from "react-router-dom";
import CommunityPage from "./pages/CommunityPage";
import FlowPage from "./pages/FlowPage";
import HomePage from "./pages/MainPage";
import DeleteAccountPage from "./pages/deleteAccountPage";
import LoginPage from "./pages/loginPage";

const Router = () => {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/community" element={<CommunityPage />} />
      <Route path="/flow/:id/">
        <Route path="" element={<FlowPage />} />
      </Route>
      <Route path="*" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/account">
        <Route path="delete" element={<DeleteAccountPage />}></Route>
      </Route>
    </Routes>
  );
};

export default Router;
