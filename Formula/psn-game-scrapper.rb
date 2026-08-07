class PsnGameScrapper < Formula
  include Language::Python::Virtualenv

  desc "Export your PSN game library to a GRAVK-compatible CSV file"
  homepage "https://github.com/olegzalipskiy/psn_game_scrapper"
  url "https://github.com/olegzalipskiy/psn_game_scrapper/archive/refs/tags/v0.1.0.tar.gz"
  # Replace with the real checksum once v0.1.0 is tagged, e.g.:
  #   curl -sL https://github.com/olegzalipskiy/psn_game_scrapper/archive/refs/tags/v0.1.0.tar.gz | shasum -a 256
  sha256 "REPLACE_WITH_RELEASE_TARBALL_SHA256"
  license "MIT"

  depends_on "python@3.12"

  resource "certifi" do
    url "https://files.pythonhosted.org/packages/a3/c2/24167ea9858356b47a87a50d39908bfdb72ceeefe0041586e704e5376b3a/certifi-2026.7.22.tar.gz"
    sha256 "741e2c3b351ddf169a738da9f2c048608ff7f2c5cc02f1ebc6b118bb090d5d55"
  end

  resource "charset-normalizer" do
    url "https://files.pythonhosted.org/packages/bd/2a/23f34ec9d04624958e137efdc394888716353190e75f25dd22c7a2c7a8aa/charset_normalizer-3.4.9.tar.gz"
    sha256 "673611bbd43f0810bec0b0f028ddeaaa501190339cac411f347ac76917c3ae7b"
  end

  resource "idna" do
    url "https://files.pythonhosted.org/packages/cd/63/9496c57188a2ee585e0f1db071d75089a11e98aa86eb99d9d7618fc1edce/idna-3.18.tar.gz"
    sha256 "ffb385a7e039654cef1ab9ef32c6fafe283c0c0467bba1d9029738ce4a14a848"
  end

  resource "pycountry" do
    url "https://files.pythonhosted.org/packages/76/57/c389fa68c50590881a75b7883eeb3dc15e9e73a0fdc001cdd45c13290c92/pycountry-24.6.1.tar.gz"
    sha256 "b61b3faccea67f87d10c1f2b0fc0be714409e8fcdcc1315613174f6466c10221"
  end

  resource "pyrate-limiter" do
    url "https://files.pythonhosted.org/packages/19/27/e564f33ea085c63d5540f707b31aeb50a4992eac2da655dc02435a760a07/pyrate_limiter-4.4.0.tar.gz"
    sha256 "2c0c720c4fa16c5d8199e4821bf34507fb49c007a25b786cec6fb94ffd0844aa"
  end

  resource "requests" do
    url "https://files.pythonhosted.org/packages/ac/c3/e2a2b89f2d3e2179abd6d00ebd70bff6273f37fb3e0cc209f48b39d00cbf/requests-2.34.2.tar.gz"
    sha256 "f288924cae4e29463698d6d60bc6a4da69c89185ad1e0bcc4104f584e960b9ed"
  end

  resource "urllib3" do
    url "https://files.pythonhosted.org/packages/53/0c/06f8b233b8fd13b9e5ee11424ef85419ba0d8ba0b3138bf360be2ff56953/urllib3-2.7.0.tar.gz"
    sha256 "231e0ec3b63ceb14667c67be60f2f2c40a518cb38b03af60abc813da26505f4c"
  end

  resource "typing-extensions" do
    url "https://files.pythonhosted.org/packages/f6/cc/6253133b5bb138fc3306cebfbda2c520f545d36b5be2c7255cc528bb45d6/typing_extensions-4.16.0.tar.gz"
    sha256 "dc983d19a509c94dba722ee6abd33940f7c05a89e243c47e907eb4db6f1a43e5"
  end

  resource "psnawp" do
    url "https://files.pythonhosted.org/packages/50/a4/231f64f6e71aab503f52745d7135af9ba27abc52daa8fa59b0359d6e6242/psnawp-3.0.3.tar.gz"
    sha256 "ef31b0a531e0918ba31bb63714839667cc69720540595f74143602f960e6501f"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"psn-export", "--help"
  end
end
