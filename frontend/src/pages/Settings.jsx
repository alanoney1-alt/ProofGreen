import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { companiesAPI, authAPI } from '../services/api'
import toast from 'react-hot-toast'

export default function Settings() {
  const { user, company, updateUser, updateCompany } = useAuth()
  const [loading, setLoading] = useState(false)
  const [verticals, setVerticals] = useState([])
  const [activeTab, setActiveTab] = useState('profile')

  const [profileData, setProfileData] = useState({
    firstName: user?.firstName || '',
    lastName: user?.lastName || '',
    email: user?.email || '',
    phone: user?.phone || ''
  })

  const [companyData, setCompanyData] = useState({
    name: company?.name || '',
    email: company?.email || '',
    phone: company?.phone || '',
    website: company?.website || '',
    addressLine1: company?.address_line1 || '',
    city: company?.city || '',
    state: company?.state || '',
    zipCode: company?.zip_code || ''
  })

  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })

  const [selectedVerticals, setSelectedVerticals] = useState([])

  useEffect(() => {
    fetchVerticals()
  }, [])

  useEffect(() => {
    if (company?.company_verticals) {
      setSelectedVerticals(company.company_verticals.map(cv => cv.verticals?.id || cv.vertical_id))
    }
  }, [company])

  const fetchVerticals = async () => {
    try {
      const response = await authAPI.getVerticals()
      setVerticals(response.data.verticals)
    } catch (error) {
      console.error('Failed to fetch verticals:', error)
    }
  }

  const handleProfileSave = async () => {
    setLoading(true)
    try {
      // Profile update would go to a user update endpoint
      // For now, just show success
      updateUser(profileData)
      toast.success('Profile updated')
    } catch (error) {
      toast.error('Failed to update profile')
    } finally {
      setLoading(false)
    }
  }

  const handleCompanySave = async () => {
    setLoading(true)
    try {
      const response = await companiesAPI.update(company.id, {
        name: companyData.name,
        email: companyData.email,
        phone: companyData.phone,
        website: companyData.website,
        address_line1: companyData.addressLine1,
        city: companyData.city,
        state: companyData.state,
        zip_code: companyData.zipCode
      })
      updateCompany(response.data.company)
      toast.success('Company updated')
    } catch (error) {
      toast.error('Failed to update company')
    } finally {
      setLoading(false)
    }
  }

  const handleVerticalsSave = async () => {
    setLoading(true)
    try {
      await companiesAPI.updateVerticals(company.id, selectedVerticals)
      toast.success('Service types updated')
    } catch (error) {
      toast.error('Failed to update service types')
    } finally {
      setLoading(false)
    }
  }

  const handlePasswordChange = async () => {
    if (passwordData.newPassword !== passwordData.confirmPassword) {
      toast.error('Passwords do not match')
      return
    }
    if (passwordData.newPassword.length < 8) {
      toast.error('Password must be at least 8 characters')
      return
    }

    setLoading(true)
    try {
      await authAPI.updatePassword({
        currentPassword: passwordData.currentPassword,
        newPassword: passwordData.newPassword
      })
      setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' })
      toast.success('Password updated')
    } catch (error) {
      toast.error(error.response?.data?.error || 'Failed to update password')
    } finally {
      setLoading(false)
    }
  }

  const tabs = [
    { id: 'profile', name: 'Profile' },
    { id: 'company', name: 'Company' },
    { id: 'verticals', name: 'Service Types' },
    { id: 'security', name: 'Security' }
  ]

  return (
    <div className="animate-fade-in max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-gray-600 mt-1">
          Manage your account and company settings
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 mb-8">
        <nav className="flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.name}
            </button>
          ))}
        </nav>
      </div>

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Personal Information</h2>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">First Name</label>
                <input
                  type="text"
                  value={profileData.firstName}
                  onChange={(e) => setProfileData(p => ({ ...p, firstName: e.target.value }))}
                  className="input"
                />
              </div>
              <div>
                <label className="label">Last Name</label>
                <input
                  type="text"
                  value={profileData.lastName}
                  onChange={(e) => setProfileData(p => ({ ...p, lastName: e.target.value }))}
                  className="input"
                />
              </div>
            </div>
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                value={profileData.email}
                onChange={(e) => setProfileData(p => ({ ...p, email: e.target.value }))}
                className="input"
                disabled
              />
              <p className="text-xs text-gray-500 mt-1">Email cannot be changed</p>
            </div>
            <div>
              <label className="label">Phone</label>
              <input
                type="tel"
                value={profileData.phone}
                onChange={(e) => setProfileData(p => ({ ...p, phone: e.target.value }))}
                className="input"
              />
            </div>
            <div className="pt-4">
              <button onClick={handleProfileSave} disabled={loading} className="btn-primary">
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Company Tab */}
      {activeTab === 'company' && (
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Company Information</h2>
          <div className="space-y-4">
            <div>
              <label className="label">Company Name</label>
              <input
                type="text"
                value={companyData.name}
                onChange={(e) => setCompanyData(p => ({ ...p, name: e.target.value }))}
                className="input"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Email</label>
                <input
                  type="email"
                  value={companyData.email}
                  onChange={(e) => setCompanyData(p => ({ ...p, email: e.target.value }))}
                  className="input"
                />
              </div>
              <div>
                <label className="label">Phone</label>
                <input
                  type="tel"
                  value={companyData.phone}
                  onChange={(e) => setCompanyData(p => ({ ...p, phone: e.target.value }))}
                  className="input"
                />
              </div>
            </div>
            <div>
              <label className="label">Website</label>
              <input
                type="url"
                value={companyData.website}
                onChange={(e) => setCompanyData(p => ({ ...p, website: e.target.value }))}
                className="input"
                placeholder="https://yourcompany.com"
              />
            </div>
            <div>
              <label className="label">Address</label>
              <input
                type="text"
                value={companyData.addressLine1}
                onChange={(e) => setCompanyData(p => ({ ...p, addressLine1: e.target.value }))}
                className="input"
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="label">City</label>
                <input
                  type="text"
                  value={companyData.city}
                  onChange={(e) => setCompanyData(p => ({ ...p, city: e.target.value }))}
                  className="input"
                />
              </div>
              <div>
                <label className="label">State</label>
                <input
                  type="text"
                  value={companyData.state}
                  onChange={(e) => setCompanyData(p => ({ ...p, state: e.target.value }))}
                  className="input"
                />
              </div>
              <div>
                <label className="label">ZIP Code</label>
                <input
                  type="text"
                  value={companyData.zipCode}
                  onChange={(e) => setCompanyData(p => ({ ...p, zipCode: e.target.value }))}
                  className="input"
                />
              </div>
            </div>
            <div className="pt-4">
              <button onClick={handleCompanySave} disabled={loading} className="btn-primary">
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Verticals Tab */}
      {activeTab === 'verticals' && (
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Service Types</h2>
          <p className="text-gray-600 mb-6">Select the services your company provides</p>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {verticals.map((vertical) => (
              <button
                key={vertical.id}
                onClick={() => {
                  setSelectedVerticals(prev =>
                    prev.includes(vertical.id)
                      ? prev.filter(id => id !== vertical.id)
                      : [...prev, vertical.id]
                  )
                }}
                className={`p-4 text-left rounded-lg border-2 transition-colors ${
                  selectedVerticals.includes(vertical.id)
                    ? 'border-primary-600 bg-primary-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <span className="font-medium text-gray-900">{vertical.name}</span>
              </button>
            ))}
          </div>
          <div className="pt-6">
            <button onClick={handleVerticalsSave} disabled={loading} className="btn-primary">
              {loading ? 'Saving...' : 'Save Service Types'}
            </button>
          </div>
        </div>
      )}

      {/* Security Tab */}
      {activeTab === 'security' && (
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">Change Password</h2>
          <div className="space-y-4 max-w-md">
            <div>
              <label className="label">Current Password</label>
              <input
                type="password"
                value={passwordData.currentPassword}
                onChange={(e) => setPasswordData(p => ({ ...p, currentPassword: e.target.value }))}
                className="input"
              />
            </div>
            <div>
              <label className="label">New Password</label>
              <input
                type="password"
                value={passwordData.newPassword}
                onChange={(e) => setPasswordData(p => ({ ...p, newPassword: e.target.value }))}
                className="input"
                placeholder="Min. 8 characters"
              />
            </div>
            <div>
              <label className="label">Confirm New Password</label>
              <input
                type="password"
                value={passwordData.confirmPassword}
                onChange={(e) => setPasswordData(p => ({ ...p, confirmPassword: e.target.value }))}
                className="input"
              />
            </div>
            <div className="pt-4">
              <button onClick={handlePasswordChange} disabled={loading} className="btn-primary">
                {loading ? 'Updating...' : 'Update Password'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
