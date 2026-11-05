# frozen_string_literal: true

# airoom.rb: formula for pipx-installable Python package
class Airoom < Formula
  desc "Shared infrastructure for AI agents and tools"
  homepage "https://github.com/zero-0o0o/airoom"
  url "https://pypi.org/packages/source/a/airoom/airoom-0.1.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256_REPLACE_WHEN_PUBLISHED_TO_PYPI"
  depends_on "pipx"
  def install
    system "pipx", "install", "--force", "--spec", cached_download, "airoom"
  end

  test do
    system "pipx", "run", "--spec", cached_download, "airoom", "--version"
  end
end