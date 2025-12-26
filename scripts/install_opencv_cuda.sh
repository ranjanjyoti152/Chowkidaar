#!/bin/bash
# =============================================================================
# OpenCV with CUDA Support - Compilation Script
# =============================================================================
# This script compiles OpenCV from source with CUDA and cuDNN support
# for GPU-accelerated video processing and computer vision
#
# System Requirements:
# - Ubuntu 20.04/22.04/24.04
# - NVIDIA GPU with CUDA Compute Capability 6.0+
# - CUDA Toolkit 11.x or 12.x
# - cuDNN 8.x or newer
# - At least 16GB RAM (32GB recommended)
# - At least 30GB free disk space
#
# Usage: ./install_opencv_cuda.sh
# =============================================================================

set -e  # Exit on any error

# Configuration
# Using OpenCV 4.x master (latest) for Video Codec SDK 13 compatibility
OPENCV_VERSION="4.x"  # Use master branch for latest SDK support
CUDA_ARCH="8.6"  # RTX A4500 compute capability
NUM_JOBS=$(nproc)
INSTALL_PREFIX="/usr/local"
BUILD_DIR="/tmp/opencv_build"
PYTHON_EXECUTABLE=$(which python3)

# Video Codec SDK path (for NVCUVID hardware video decoding)
# Download from: https://developer.nvidia.com/nvidia-video-codec-sdk
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VIDEO_CODEC_SDK="${PROJECT_ROOT}/Video_Codec_SDK_13.0.19"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root for system-wide install
check_permissions() {
    if [[ $EUID -ne 0 ]]; then
        log_warning "Not running as root. Will need sudo for installation."
    fi
}

# Check NVIDIA GPU and CUDA
check_nvidia() {
    log_info "Checking NVIDIA GPU and CUDA..."
    
    if ! command -v nvidia-smi &> /dev/null; then
        log_error "nvidia-smi not found. Please install NVIDIA drivers."
        exit 1
    fi
    
    GPU_INFO=$(nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | head -1)
    log_info "GPU: $GPU_INFO"
    
    if ! command -v nvcc &> /dev/null; then
        log_error "CUDA toolkit not found. Please install CUDA."
        exit 1
    fi
    
    CUDA_VERSION=$(nvcc --version | grep "release" | sed 's/.*release \([0-9]*\.[0-9]*\).*/\1/')
    log_info "CUDA Version: $CUDA_VERSION"
    
    # Get compute capability
    COMPUTE_CAP=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | head -1)
    if [[ -n "$COMPUTE_CAP" ]]; then
        log_info "GPU Compute Capability: $COMPUTE_CAP"
        CUDA_ARCH="$COMPUTE_CAP"
    fi
}

# Setup Video Codec SDK headers for NVCUVID support
setup_video_codec_sdk() {
    log_info "Setting up NVIDIA Video Codec SDK for NVCUVID support..."
    
    CUDA_INCLUDE="/usr/local/cuda/include"
    if [[ ! -d "$CUDA_INCLUDE" ]]; then
        CUDA_INCLUDE="$(dirname $(dirname $(which nvcc)))/include"
    fi
    
    if [[ -d "$VIDEO_CODEC_SDK" ]]; then
        log_info "Found Video Codec SDK at: $VIDEO_CODEC_SDK"
        
        # Check for headers
        if [[ -f "$VIDEO_CODEC_SDK/Interface/nvcuvid.h" ]]; then
            # Copy headers to CUDA include directory
            sudo cp -v "$VIDEO_CODEC_SDK/Interface/nvcuvid.h" "$CUDA_INCLUDE/" 2>/dev/null || true
            sudo cp -v "$VIDEO_CODEC_SDK/Interface/cuviddec.h" "$CUDA_INCLUDE/" 2>/dev/null || true
            sudo cp -v "$VIDEO_CODEC_SDK/Interface/nvEncodeAPI.h" "$CUDA_INCLUDE/" 2>/dev/null || true
            log_success "Video Codec SDK headers installed to $CUDA_INCLUDE"
        else
            log_warning "Video Codec SDK headers not found in $VIDEO_CODEC_SDK/Interface/"
            log_info "NVCUVID hardware decoding may not be available"
        fi
    else
        log_warning "Video Codec SDK not found at: $VIDEO_CODEC_SDK"
        log_info "Download from: https://developer.nvidia.com/nvidia-video-codec-sdk"
        log_info "Extract to: $VIDEO_CODEC_SDK"
        log_info "NVCUVID hardware decoding may not be available"
    fi
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies..."
    
    sudo apt-get update
    sudo apt-get install -y \
        build-essential \
        cmake \
        git \
        pkg-config \
        libgtk-3-dev \
        libavcodec-dev \
        libavformat-dev \
        libswscale-dev \
        libv4l-dev \
        libxvidcore-dev \
        libx264-dev \
        libjpeg-dev \
        libpng-dev \
        libtiff-dev \
        libatlas-base-dev \
        gfortran \
        openexr \
        libdc1394-dev \
        libopenexr-dev \
        libgstreamer-plugins-base1.0-dev \
        libgstreamer1.0-dev \
        python3-dev \
        python3-numpy \
        libtbb-dev \
        libopenblas-dev \
        liblapack-dev \
        libeigen3-dev \
        libhdf5-dev \
        libprotobuf-dev \
        protobuf-compiler \
        libgoogle-glog-dev \
        libgflags-dev \
        libgphoto2-dev \
        libwebp-dev \
        libva-dev \
        libvdpau-dev \
        libnvidia-decode-$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1 | cut -d'.' -f1) \
        libnvidia-encode-$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1 | cut -d'.' -f1) \
        2>/dev/null || true
    
    log_success "Dependencies installed"
}

# Download OpenCV source
download_opencv() {
    log_info "Downloading OpenCV ${OPENCV_VERSION}..."
    
    mkdir -p "$BUILD_DIR"
    cd "$BUILD_DIR"
    
    # Download OpenCV
    if [[ ! -d "opencv" ]]; then
        git clone --depth 1 --branch ${OPENCV_VERSION} https://github.com/opencv/opencv.git
    else
        log_info "OpenCV source already exists, skipping download"
    fi
    
    # Download OpenCV contrib (extra modules)
    if [[ ! -d "opencv_contrib" ]]; then
        git clone --depth 1 --branch ${OPENCV_VERSION} https://github.com/opencv/opencv_contrib.git
    else
        log_info "OpenCV contrib already exists, skipping download"
    fi
    
    log_success "OpenCV source downloaded"
}

# Configure and build OpenCV
build_opencv() {
    log_info "Configuring OpenCV with CUDA support..."
    
    cd "$BUILD_DIR/opencv"
    mkdir -p build
    cd build
    
    # Find CUDA paths
    CUDA_PATH=$(dirname $(dirname $(which nvcc)))
    CUDNN_PATH="/usr"
    
    # Get Python paths
    PYTHON_INCLUDE=$(python3 -c "from distutils.sysconfig import get_python_inc; print(get_python_inc())")
    PYTHON_LIBRARY=$(python3 -c "import distutils.sysconfig as sysconfig; print(sysconfig.get_config_var('LIBDIR'))")/libpython3.$(python3 -c "import sys; print(sys.version_info.minor)").so
    PYTHON_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
    
    cmake \
        -D CMAKE_BUILD_TYPE=RELEASE \
        -D CMAKE_INSTALL_PREFIX=${INSTALL_PREFIX} \
        -D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib/modules \
        -D WITH_CUDA=ON \
        -D WITH_CUDNN=ON \
        -D OPENCV_DNN_CUDA=ON \
        -D ENABLE_FAST_MATH=ON \
        -D CUDA_FAST_MATH=ON \
        -D CUDA_ARCH_BIN="${CUDA_ARCH}" \
        -D CUDA_ARCH_PTX="" \
        -D WITH_CUBLAS=ON \
        -D WITH_CUFFT=ON \
        -D WITH_NVCUVID=ON \
        -D WITH_NVCUVENC=ON \
        -D WITH_TBB=ON \
        -D WITH_V4L=ON \
        -D WITH_GSTREAMER=ON \
        -D WITH_OPENGL=ON \
        -D WITH_FFMPEG=ON \
        -D BUILD_opencv_python3=ON \
        -D PYTHON3_EXECUTABLE=${PYTHON_EXECUTABLE} \
        -D PYTHON3_INCLUDE_DIR=${PYTHON_INCLUDE} \
        -D PYTHON3_PACKAGES_PATH=${PYTHON_PACKAGES} \
        -D OPENCV_GENERATE_PKGCONFIG=ON \
        -D BUILD_EXAMPLES=OFF \
        -D BUILD_TESTS=OFF \
        -D BUILD_PERF_TESTS=OFF \
        -D BUILD_opencv_apps=OFF \
        -D INSTALL_PYTHON_EXAMPLES=OFF \
        -D OPENCV_ENABLE_NONFREE=ON \
        ..
    
    log_info "Building OpenCV with ${NUM_JOBS} parallel jobs..."
    log_warning "This may take 30-60 minutes depending on your system"
    
    make -j${NUM_JOBS}
    
    log_success "OpenCV build completed"
}

# Install OpenCV
install_opencv() {
    log_info "Installing OpenCV..."
    
    cd "$BUILD_DIR/opencv/build"
    sudo make install
    sudo ldconfig
    
    # Create symlink for Python if needed
    PYTHON_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])")
    if [[ -f "${INSTALL_PREFIX}/lib/python3.*/site-packages/cv2"* ]]; then
        sudo ln -sf ${INSTALL_PREFIX}/lib/python3.*/site-packages/cv2* ${PYTHON_PACKAGES}/ 2>/dev/null || true
    fi
    
    log_success "OpenCV installed"
}

# Verify installation
verify_installation() {
    log_info "Verifying OpenCV CUDA installation..."
    
    python3 << 'EOF'
import cv2

print(f"OpenCV Version: {cv2.__version__}")

# Check CUDA support
cuda_devices = cv2.cuda.getCudaEnabledDeviceCount() if hasattr(cv2, 'cuda') else 0
print(f"CUDA Enabled Devices: {cuda_devices}")

if cuda_devices > 0:
    print("✅ OpenCV CUDA support is working!")
    
    # Print build info
    build_info = cv2.getBuildInformation()
    
    # Check for CUDA in build info
    if 'CUDA' in build_info:
        print("\nCUDA Build Info:")
        for line in build_info.split('\n'):
            if 'CUDA' in line or 'cuDNN' in line:
                print(f"  {line.strip()}")
else:
    print("❌ CUDA support not available in OpenCV")
    exit(1)
EOF

    if [[ $? -eq 0 ]]; then
        log_success "OpenCV with CUDA is working correctly!"
    else
        log_error "OpenCV CUDA verification failed"
        exit 1
    fi
}

# Cleanup
cleanup() {
    log_info "Cleaning up build files..."
    
    read -p "Delete build directory ($BUILD_DIR)? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$BUILD_DIR"
        log_success "Build directory removed"
    else
        log_info "Build directory kept at $BUILD_DIR"
    fi
}

# Print usage instructions
print_usage() {
    echo ""
    echo "=============================================="
    echo "          OpenCV CUDA Installation Complete   "
    echo "=============================================="
    echo ""
    echo "OpenCV ${OPENCV_VERSION} with CUDA support has been installed!"
    echo ""
    echo "To use in Python:"
    echo "  import cv2"
    echo "  print(cv2.cuda.getCudaEnabledDeviceCount())"
    echo ""
    echo "Example GPU-accelerated video capture:"
    echo "  cap = cv2.VideoCapture('video.mp4', cv2.CAP_FFMPEG)"
    echo "  # Or use CUDA-accelerated decoder"
    echo "  gpu_frame = cv2.cuda_GpuMat()"
    echo ""
    echo "For Chowkidaar NVR, restart the backend to use GPU acceleration."
    echo ""
}

# Main execution
main() {
    echo "=============================================="
    echo "  OpenCV with CUDA - Installation Script     "
    echo "=============================================="
    echo ""
    
    check_permissions
    check_nvidia
    
    echo ""
    log_info "This script will compile OpenCV ${OPENCV_VERSION} with CUDA support"
    log_info "Build will use ${NUM_JOBS} parallel jobs"
    log_info "Installation prefix: ${INSTALL_PREFIX}"
    log_warning "This process may take 30-60 minutes"
    echo ""
    
    read -p "Continue with installation? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Installation cancelled"
        exit 0
    fi
    
    install_dependencies
    setup_video_codec_sdk
    download_opencv
    build_opencv
    install_opencv
    verify_installation
    cleanup
    print_usage
}

# Run main function
main "$@"
