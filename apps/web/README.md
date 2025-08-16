# GPUCloud Dashboard

A professional, dark-themed dashboard for managing AWS GPU and CPU instances with real-time integration to your backend API.

## ✨ Features

### 🎨 **Professional UI Design**
- **Dark Theme**: Modern black/purple color scheme matching your design
- **Responsive Layout**: Works on all device sizes
- **Interactive Components**: Hover effects, animations, and smooth transitions

### 🚀 **Real Backend Integration**
- **Live Pod Management**: View, start, stop, and terminate real EC2 instances
- **Real-time Catalog**: Browse AWS instance types with live pricing and markup
- **Authentication**: JWT-based login/signup system
- **Credit Management**: View balance and spending in real-time

### 🔧 **Core Functionality**
- **Instance Deployment**: One-click deployment from the AWS catalog
- **Pod Monitoring**: Real-time status updates (running, stopped, error, etc.)
- **Search & Filter**: Find pods by name, ID, or GPU type
- **Cost Tracking**: Per-minute billing with hourly rate display

## 🏗️ Architecture

### **Frontend Stack**
- **Next.js 14**: React framework with App Router
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first CSS framework
- **Lucide React**: Beautiful, consistent icons

### **Components Structure**
```
components/
├── Dashboard.tsx      # Main dashboard layout with sidebar
├── PodManager.tsx     # Pod management and deployment
├── Login.tsx          # Authentication interface
└── contexts/
    └── AuthContext.tsx # JWT authentication state
```

### **Backend Integration**
- **API Endpoints**: Connects to your FastAPI backend
- **Real-time Data**: Fetches live pod status and catalog
- **Authentication**: JWT token management
- **Error Handling**: Graceful fallbacks and user feedback

## 🚀 Getting Started

### **Prerequisites**
- Node.js 18+ and npm
- Your backend API running on `http://localhost:8080`

### **Installation**
```bash
cd apps/web
npm install
```

### **Development**
```bash
npm run dev
```

The dashboard will be available at `http://localhost:3000`

### **Build for Production**
```bash
npm run build
npm start
```

## 🔐 Authentication

### **User Flow**
1. **Sign Up**: Create a new account with email/password
2. **Login**: Authenticate with existing credentials
3. **JWT Token**: Automatic token management and refresh
4. **Logout**: Secure session termination

### **Security Features**
- JWT tokens stored in localStorage
- Automatic token validation
- Secure API calls with Authorization headers

## 📊 Dashboard Features

### **Left Sidebar**
- **Brand**: vsl.and logo and branding
- **Credit Balance**: Real-time balance display
- **Navigation**: Home, Explore, Hub, Manage, Account
- **Referral System**: $ Refer & Earn button

### **Main Content Area**
- **Pod Management**: View and manage all your instances
- **Deploy Button**: Launch new instances from catalog
- **Search & Filter**: Find specific pods quickly
- **Real-time Status**: Live updates on pod states

### **Pod Cards**
- **Instance Details**: Type, CPU, RAM, GPU specifications
- **Network Info**: Public IP, region, global network settings
- **Cost Information**: Hourly rate and per-minute pricing
- **Action Buttons**: Start, terminate, logs, view

## 🔌 API Integration

### **Backend Endpoints Used**
- `POST /v1/auth/signup` - User registration
- `POST /v1/auth/login` - User authentication
- `GET /v1/catalog/aws` - Instance catalog with pricing
- `POST /v1/catalog/aws/launch` - Deploy new instances
- `GET /v1/pods` - List user pods
- `POST /v1/pods/{id}/stop` - Terminate pods

### **Data Flow**
1. **Authentication**: User logs in, receives JWT token
2. **Catalog Fetch**: Retrieves AWS instance types and pricing
3. **Pod Management**: CRUD operations on user instances
4. **Real-time Updates**: Live status monitoring and cost tracking

## 🎯 Key Benefits

### **For Users**
- **Professional Interface**: Enterprise-grade UI/UX
- **Real-time Management**: Live pod monitoring and control
- **Cost Transparency**: Clear pricing and usage tracking
- **One-click Deployment**: Simple instance provisioning

### **For Developers**
- **Type Safety**: Full TypeScript support
- **Component Reusability**: Modular, maintainable code
- **API Integration**: Seamless backend connectivity
- **Responsive Design**: Mobile-first approach

## 🔧 Customization

### **Styling**
- **Tailwind Classes**: Easy color and layout modifications
- **CSS Variables**: Centralized theme management
- **Component Props**: Flexible component configuration

### **Features**
- **New Components**: Easy to add new dashboard sections
- **API Endpoints**: Simple to integrate additional backend features
- **Authentication**: Extensible auth system for different providers

## 🚀 Deployment

### **Environment Variables**
```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8080

# Authentication
NEXTAUTH_SECRET=your-secret-key
NEXTAUTH_URL=http://localhost:3000
```

### **Build Process**
```bash
npm run build    # Create production build
npm start        # Start production server
```

## 📱 Mobile Support

- **Responsive Design**: Optimized for all screen sizes
- **Touch-friendly**: Mobile-optimized interactions
- **Progressive Web App**: Can be installed on mobile devices

## 🔍 Troubleshooting

### **Common Issues**
1. **API Connection**: Ensure backend is running on port 8080
2. **Authentication**: Check JWT token validity
3. **CORS**: Verify backend CORS settings
4. **Build Errors**: Check Node.js version compatibility

### **Debug Mode**
```bash
# Enable detailed logging
DEBUG=* npm run dev
```

## 🎉 Success!

Your dashboard is now fully integrated with your working AWS backend! Users can:

✅ **Browse** AWS instance catalog with real pricing  
✅ **Deploy** instances with one click  
✅ **Monitor** running pods in real-time  
✅ **Manage** costs and usage transparently  
✅ **Scale** workloads seamlessly  

The interface provides a professional, enterprise-grade experience that matches your backend's capabilities perfectly! 🚀
