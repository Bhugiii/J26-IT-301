import { useEffect } from 'react'
import { Link, Route, Routes, useLocation } from 'react-router-dom'
import Overview from './pages/Overview'
import Destinations from './pages/Destinations'
import DestinationPage from './pages/Destination'
import Compare from './pages/Compare'
import Layout from './components/Layout'

function ScrollTop() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])
  return null
}

export default function App() {
  return (
    <>
      <ScrollTop />
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/destinations" element={<Destinations />} />
        <Route path="/destination/:name" element={<DestinationPage />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="*" element={
          <Layout crumbs={['Not found']}>
            <div className="card mx-auto mt-10 max-w-lg p-8 text-center">
              <h1 className="font-display text-[22px] font-bold">This page took a scenic detour</h1>
              <Link to="/" className="btn-primary mt-4">Back to overview</Link>
            </div>
          </Layout>
        } />
      </Routes>
    </>
  )
}
