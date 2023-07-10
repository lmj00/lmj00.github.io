class ModifiedDateGenerator < Jekyll::Generator
  def generate(site)
    after_date = Time.new(2023, 7, 11, 9)
    site.posts.docs.each do |post|
      if File.mtime(post.path) > after_date
        post.data["modified_date"] = File.mtime(post.path)
      end
    end
  end
end